data "archive_file" "common_layer" {
  type        = "zip"
  source_dir  = "${path.module}/../../../shared"
  output_path = "${path.module}/attendance-common-layer.zip"
}

resource "aws_kms_key" "attendance" {
  description             = "Attendance ${var.env} data encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "foundation"
  }
}

resource "aws_kms_alias" "attendance" {
  name          = "alias/attendance-${var.env}"
  target_key_id = aws_kms_key.attendance.key_id
}

resource "aws_s3_bucket" "raw" {
  bucket        = "attendance-${var.env}-${var.account_id}-raw"
  force_destroy = false

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "raw-biometric"
  }
}

resource "aws_s3_bucket" "reports" {
  bucket        = "attendance-${var.env}-${var.account_id}-reports"
  force_destroy = false

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "reports"
  }
}

resource "aws_s3_bucket" "web" {
  bucket        = "attendance-${var.env}-${var.account_id}-web"
  force_destroy = false

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "web"
  }
}

locals {
  buckets = {
    raw     = aws_s3_bucket.raw.id
    reports = aws_s3_bucket.reports.id
    web     = aws_s3_bucket.web.id
  }
  bucket_arns = {
    raw     = aws_s3_bucket.raw.arn
    reports = aws_s3_bucket.reports.arn
  }
}

resource "aws_s3_bucket_public_access_block" "buckets" {
  for_each = local.buckets

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "buckets" {
  for_each = local.buckets

  bucket = each.value

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.attendance.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_cors_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["POST"]
    allowed_origins = var.raw_upload_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 300
  }
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    id     = "expire-captures"
    status = "Enabled"

    filter {
      prefix = "captures/"
    }

    expiration {
      days = 1
    }
  }

  rule {
    id     = "expire-enrollment-photos"
    status = "Enabled"

    filter {
      prefix = "enroll/"
    }

    expiration {
      days = 1
    }
  }

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

data "aws_iam_policy_document" "bucket_tls" {
  for_each = local.bucket_arns

  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:*"]
    resources = [each.value, "${each.value}/*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "buckets" {
  for_each = local.bucket_arns

  bucket = local.buckets[each.key]
  policy = data.aws_iam_policy_document.bucket_tls[each.key].json
}

resource "aws_sns_topic" "alerts" {
  name              = "attendance-${var.env}-alerts"
  kms_master_key_id = aws_kms_key.attendance.arn

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "alerts"
  }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_lambda_layer_version" "common" {
  layer_name          = "attendance-${var.env}-common"
  filename            = data.archive_file.common_layer.output_path
  source_code_hash    = data.archive_file.common_layer.output_base64sha256
  compatible_runtimes = ["python3.12"]
  description         = "Shared timezone, configuration, response and attendance helpers."
}

