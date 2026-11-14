import boto3
import pytest
from moto import mock_aws

from services.recognition.faces_delete import handler as faces_delete


class FakeRekognition:
    def __init__(self, response=None):
        self.response = response
        self.calls = []

    def delete_faces(self, **kwargs):
        self.calls.append(kwargs["FaceIds"])
        if self.response is not None:
            return self.response
        return {"DeletedFaces": kwargs["FaceIds"]}


@pytest.fixture
def resources(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
        monkeypatch.setenv("TABLE_AUDIT", "audit")
        monkeypatch.setenv("COLLECTION_ID", "attendance-dev-faces")
        db = boto3.resource("dynamodb", region_name="us-east-1")
        employees = db.create_table(
            TableName="employees",
            KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        audit = db.create_table(
            TableName="audit",
            KeySchema=[{"AttributeName": "audit_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "audit_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield employees, audit


def admin_event(employee_id="EMP001"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {
                "cognito:groups": "[admin]",
                "cognito:username": "hr-admin",
            }}}
        },
        "pathParameters": {"employee_id": employee_id},
    }


def test_face_deletion_requires_employee_deactivation(resources, monkeypatch):
    employees, _ = resources
    employees.put_item(Item={
        "employee_id": "EMP001", "active": True,
        "face_ids": ["face-001"], "photo_count": 1,
    })
    fake = FakeRekognition()
    monkeypatch.setattr(faces_delete.boto3, "client", lambda *args, **kwargs: fake)

    response = faces_delete.lambda_handler(admin_event(), None)

    assert response["statusCode"] == 409
    assert fake.calls == []
    assert employees.get_item(Key={"employee_id": "EMP001"})["Item"]["face_ids"] == ["face-001"]


def test_face_deletion_is_audited_and_retry_safe(resources, monkeypatch):
    employees, audit = resources
    employees.put_item(Item={
        "employee_id": "EMP001", "active": False,
        "face_ids": ["face-001", "face-002"], "photo_count": 2,
    })
    fake = FakeRekognition()
    monkeypatch.setattr(faces_delete.boto3, "client", lambda *args, **kwargs: fake)

    response = faces_delete.lambda_handler(admin_event(), None)
    item = employees.get_item(Key={"employee_id": "EMP001"})["Item"]
    audit_items = audit.scan()["Items"]

    assert response["statusCode"] == 200
    assert item["face_ids"] == []
    assert item["photo_count"] == 0
    assert item["last_faces_delete_audit_id"] == audit_items[0]["audit_id"]
    assert audit_items[0]["action"] == "faces_delete"
    assert audit_items[0]["actor"] == "hr-admin"
    assert audit_items[0]["old"]["face_ids"] == ["face-001", "face-002"]
    assert fake.calls == [["face-001", "face-002"]]

    retry = faces_delete.lambda_handler(admin_event(), None)
    assert retry["statusCode"] == 200
    assert fake.calls == [["face-001", "face-002"]]
    assert len(audit.scan()["Items"]) == 1


def test_face_deletion_does_not_clear_ids_when_rekognition_reports_failure(resources, monkeypatch):
    employees, audit = resources
    employees.put_item(Item={
        "employee_id": "EMP001", "active": False,
        "face_ids": ["face-001"], "photo_count": 1,
    })
    fake = FakeRekognition(response={
        "DeletedFaces": [],
        "UnsuccessfulFaceDeletions": [{
            "FaceId": "face-001", "Reason": "INTERNAL_ERROR",
        }],
    })
    monkeypatch.setattr(faces_delete.boto3, "client", lambda *args, **kwargs: fake)

    response = faces_delete.lambda_handler(admin_event(), None)
    item = employees.get_item(Key={"employee_id": "EMP001"})["Item"]

    assert response["statusCode"] == 500
    assert item["face_ids"] == ["face-001"]
    assert item["photo_count"] == 1
    assert audit.scan()["Items"] == []


def test_face_deletion_treats_already_missing_face_as_deleted(resources, monkeypatch):
    employees, audit = resources
    employees.put_item(Item={
        "employee_id": "EMP001", "active": False,
        "face_ids": ["face-001"], "photo_count": 1,
    })
    fake = FakeRekognition(response={
        "DeletedFaces": [],
        "UnsuccessfulFaceDeletions": [{
            "FaceId": "face-001", "Reason": "FACE_NOT_FOUND",
        }],
    })
    monkeypatch.setattr(faces_delete.boto3, "client", lambda *args, **kwargs: fake)

    response = faces_delete.lambda_handler(admin_event(), None)
    item = employees.get_item(Key={"employee_id": "EMP001"})["Item"]

    assert response["statusCode"] == 200
    assert item["face_ids"] == []
    assert item["photo_count"] == 0
    assert len(audit.scan()["Items"]) == 1
