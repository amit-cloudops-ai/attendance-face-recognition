"""Admin API for retrieving JSON summaries and short-lived CSV download links."""
from __future__ import annotations

import os
import re
from datetime import date

import boto3
from botocore.exceptions import ClientError

from services.data.common import error, require_admin, response

DAILY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEKLY_RE = re.compile(r"^\d{4}-W\d{2}$")


def handler(event, context):
    del context
    try:
        require_admin(event)
    except PermissionError as exc:
        return error(403, "forbidden", str(exc))
    except ImportError:
        return error(503, "auth_unavailable", "Shared admin authentication is not deployed yet")

    params = event.get("queryStringParameters") or {}
    report_type = params.get("type")
    period = params.get("period", "")
    if report_type == "daily" and DAILY_RE.fullmatch(period):
        try:
            date.fromisoformat(period)
        except ValueError:
            return error(400, "validation_error", "period must be a valid YYYY-MM-DD date")
        key = f"reports/daily/{period}"
    elif report_type == "weekly" and WEEKLY_RE.fullmatch(period):
        try:
            year, week = period.split("-W")
            date.fromisocalendar(int(year), int(week), 1)
        except ValueError:
            return error(400, "validation_error", "period must be a valid ISO week")
        key = f"reports/weekly/{period}"
    else:
        return error(400, "validation_error", "type must be daily or weekly and period must match its format")

    bucket = os.getenv("BUCKET_REPORTS")
    if not bucket:
        return error(500, "configuration_error", "Reports bucket is not configured")
    s3 = boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION", "ap-south-1"),
        config=__import__("botocore.config", fromlist=["Config"]).Config(signature_version="s3v4"),
    )
    try:
        result = s3.get_object(Bucket=bucket, Key=f"{key}.json")
        import json

        summary = json.loads(result["Body"].read().decode("utf-8"))
        csv_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": f"{key}.csv"},
            ExpiresIn=300,
        )
        return response(200, {"summary": summary, "csv_url": csv_url})
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404", "NotFound"}:
            return error(404, "not_found", "The requested report has not been generated")
        return error(500, "storage_error", "Unable to read the requested report")
