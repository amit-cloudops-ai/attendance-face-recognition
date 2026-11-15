"""Atomic transaction adapter for Moto, accepting resource-native and AV values."""
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError


def install_transaction_emulator(monkeypatch, db):
    """Emulate TransactWriteItems atomically using Moto's supported item APIs.

    The real boto3 DynamoDB resource client transforms native values into
    AttributeValue structures before sending the request. This test adapter
    intercepts the client method before those event handlers run, so it accepts
    native values and legacy AttributeValue maps, preflights conditions, and
    rolls back all touched tables if any action fails.
    """
    client = db.meta.client
    deserializer = TypeDeserializer()

    attribute_value_types = {"S", "N", "B", "BOOL", "NULL", "M", "L", "SS", "NS", "BS"}

    def decode_value(value):
        if (
            isinstance(value, dict)
            and len(value) == 1
            and next(iter(value)) in attribute_value_types
        ):
            return deserializer.deserialize(value)
        return value

    def decode(item):
        return {key: decode_value(value) for key, value in item.items()}

    def snapshot(table):
        items = []
        response = table.scan(ConsistentRead=True)
        items.extend(response.get("Items", []))
        while response.get("LastEvaluatedKey"):
            response = table.scan(
                ConsistentRead=True, ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))
        return items

    def restore(table, items):
        keys = [entry["AttributeName"] for entry in table.key_schema]
        for current in snapshot(table):
            table.delete_item(Key={key: current[key] for key in keys})
        for item in items:
            table.put_item(Item=item)

    def transact_write_items(TransactItems, **kwargs):
        tables = {}
        for entry in TransactItems:
            operation = next(iter(entry.values()))
            table_name = operation["TableName"]
            tables[table_name] = db.Table(table_name)
        before = {name: snapshot(table) for name, table in tables.items()}
        try:
            for entry in TransactItems:
                action, operation = next(iter(entry.items()))
                table = tables[operation["TableName"]]
                if action == "ConditionCheck":
                    key = decode(operation["Key"])
                    current = table.get_item(Key=key, ConsistentRead=True).get("Item")
                    if not current:
                        raise ClientError(
                            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Condition failed"}},
                            "ConditionCheck",
                        )
                    names_map = dict(operation.get("ExpressionAttributeNames") or {})
                    values_map = decode(operation.get("ExpressionAttributeValues") or {})
                    guard_name = "#__transaction_guard"
                    guard_value = ":__transaction_guard"
                    names_map[guard_name] = "active"
                    values_map[guard_value] = current.get("active")
                    table.update_item(
                        Key=key,
                        UpdateExpression=f"SET {guard_name}={guard_value}",
                        ConditionExpression=operation["ConditionExpression"],
                        ExpressionAttributeNames=names_map,
                        ExpressionAttributeValues=values_map,
                    )
                elif action == "Put":
                    args = {"Item": decode(operation["Item"])}
                    if operation.get("ConditionExpression"):
                        args["ConditionExpression"] = operation["ConditionExpression"]
                    if operation.get("ExpressionAttributeNames"):
                        args["ExpressionAttributeNames"] = operation["ExpressionAttributeNames"]
                    if operation.get("ExpressionAttributeValues"):
                        args["ExpressionAttributeValues"] = decode(operation["ExpressionAttributeValues"])
                    table.put_item(**args)
                elif action == "Update":
                    args = {
                        "Key": decode(operation["Key"]),
                        "UpdateExpression": operation["UpdateExpression"],
                    }
                    if operation.get("ConditionExpression"):
                        args["ConditionExpression"] = operation["ConditionExpression"]
                    if operation.get("ExpressionAttributeNames"):
                        args["ExpressionAttributeNames"] = operation["ExpressionAttributeNames"]
                    if operation.get("ExpressionAttributeValues"):
                        args["ExpressionAttributeValues"] = decode(operation["ExpressionAttributeValues"])
                    table.update_item(**args)
                else:
                    raise AssertionError(f"Unexpected transaction action: {action}")
        except ClientError as exc:
            for name, table in tables.items():
                restore(table, before[name])
            code = exc.response.get("Error", {}).get("Code")
            if code == "ConditionalCheckFailedException":
                reasons = [{"Code": "ConditionalCheckFailed", "Message": "The conditional request failed"}]
                reasons.extend({"Code": "None"} for _ in range(len(TransactItems) - 1))
                raise ClientError(
                    {
                        "Error": {
                            "Code": "TransactionCanceledException",
                            "Message": "Transaction cancelled because a condition failed",
                        },
                        "CancellationReasons": reasons,
                    },
                    "TransactWriteItems",
                ) from exc
            raise
        except Exception:
            for name, table in tables.items():
                restore(table, before[name])
            raise
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(client, "transact_write_items", transact_write_items)
