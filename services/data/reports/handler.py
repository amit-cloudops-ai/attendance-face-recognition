"""Read a generated daily/weekly report and return a short-lived CSV URL."""
import json
import logging
import os
import re

import boto3
from attendance_common.auth import require_group
from attendance_common.responses import error, ok
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")
_DAILY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WEEKLY = re.compile(r"^(\d{4})-W(\d{2})$")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _valid_period(kind, period):
    if kind == "daily":
        if not _DAILY.fullmatch(period):
            return False
        try:
            from datetime import date
            return date.fromisoformat(period).isoformat() == period
        except ValueError:
            return False
    if kind == "weekly":
        match = _WEEKLY.fullmatch(period)
        if not match:
            return False
        try:
            from datetime import date
            date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
            return True
        except ValueError:
            return False
    return False


def _not_found(exc: ClientError) -> bool:
    code = exc.response.get("Error", {}).get("Code")
    return code in {"NoSuchKey", "NotFound", "404"} or exc.response.get(
        "ResponseMetadata", {}
    ).get("HTTPStatusCode") == 404


def lambda_handler(event, context):
    event = event or {}
    denied = require_group(event, "admin")
    if denied:
        return denied
    params = event.get("queryStringParameters") or {}
    kind = params.get("type")
    period = params.get("period")
    if kind not in {"daily", "weekly"} or not isinstance(period, str) or not _valid_period(kind, period):
        return error(400, "invalid_report_period", "Provide type=daily|weekly and a valid period.")
    bucket = _required_env("BUCKET_REPORTS")
    json_key = f"reports/{kind}/{period}.json"
    csv_key = f"reports/{kind}/{period}.csv"
    s3 = boto3.client("s3", region_name=_region())
    try:
        response = s3.get_object(Bucket=bucket, Key=json_key)
        summary = json.loads(response["Body"].read())
    except ClientError as exc:
        if _not_found(exc):
            return error(404, "report_not_found", "The requested report has not been generated.")
        LOGGER.error("Report retrieval failed (%s)", exc.response.get("Error", {}).get("Code"))
        return error(500, "internal_error", "Unable to retrieve the report.")
    except (ValueError, KeyError):
        return error(500, "invalid_report", "The generated report could not be read.")

    csv_url = None
    try:
        s3.head_object(Bucket=bucket, Key=csv_key)
        csv_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": csv_key},
            ExpiresIn=300,
        )
    except ClientError as exc:
        if not _not_found(exc):
            LOGGER.error("CSV link generation failed (%s)", exc.response.get("Error", {}).get("Code"))
            return error(500, "internal_error", "Unable to prepare the CSV download.")
    return ok({"summary": summary, "csv_url": csv_url})
