terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  prefix = "attendance-${var.env}-"
  default_settings = {
    pk                      = { S = "SETTINGS" }
    face_match_threshold    = { N = "95" }
    min_brightness          = { N = "40" }
    min_sharpness           = { N = "40" }
    grace_minutes           = { N = "15" }
    debounce_minutes        = { N = "10" }
    weekend_days            = { L = [{ N = "6" }, { N = "7" }] }
    max_photos_per_employee = { N = "5" }
  }
  scheduler_enabled = var.daily_job_arn != "" && var.weekly_job_arn != ""
  route_keys = {
    "GET /api/admin/employees"                  = "employees"
    "GET /api/admin/employees/{employee_id}"    = "employees"
    "POST /api/admin/employees"                 = "employees"
    "DELETE /api/admin/employees/{employee_id}" = "employees"
    "GET /api/admin/attendance"                 = "attendance_query"
    "GET /api/admin/reports"                    = "reports"
    "POST /api/admin/attendance/override"       = "override"
    "GET /api/admin/settings"                   = "settings"
    "PUT /api/admin/settings"                   = "settings"
  }
  api_routes = {
    for route, key in local.route_keys : route => {
      function_name = var.api_lambdas[key].function_name
      invoke_arn    = var.api_lambdas[key].invoke_arn
      group         = "admin"
    } if contains(keys(var.api_lambdas), key)
  }
}

resource "aws_dynamodb_table" "employees" {
  name                        = "${local.prefix}employees"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "employee_id"
  deletion_protection_enabled = var.env == "prod"

  attribute {
    name = "employee_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "attendance" {
  name                        = "${local.prefix}attendance"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "employee_id"
  range_key                   = "date"
  deletion_protection_enabled = var.env == "prod"

  attribute {
    name = "employee_id"
    type = "S"
  }

  attribute {
    name = "date"
    type = "S"
  }

  global_secondary_index {
    name            = "date-index"
    hash_key        = "date"
    range_key       = "employee_id"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "scan_results" {
  name                        = "${local.prefix}scan-results"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "request_id"
  deletion_protection_enabled = var.env == "prod"

  attribute {
    name = "request_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "config" {
  name                        = "${local.prefix}config"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "pk"
  deletion_protection_enabled = var.env == "prod"

  attribute {
    name = "pk"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table" "audit" {
  name                        = "${local.prefix}audit"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "audit_id"
  deletion_protection_enabled = var.env == "prod"

  attribute {
    name = "audit_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_dynamodb_table_item" "default_settings" {
  table_name = aws_dynamodb_table.config.name
  hash_key   = aws_dynamodb_table.config.hash_key
  item       = jsonencode(local.default_settings)

  lifecycle {
    ignore_changes = [item]
  }
}

resource "aws_iam_role" "scheduler" {
  count = local.scheduler_enabled ? 1 : 0
  name  = "${local.prefix}scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  count = local.scheduler_enabled ? 1 : 0
  name  = "${local.prefix}scheduler-invoke"
  role  = aws_iam_role.scheduler[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = [var.daily_job_arn, var.weekly_job_arn]
    }]
  })
}

resource "aws_scheduler_schedule" "daily" {
  count                        = local.scheduler_enabled ? 1 : 0
  name                         = "${local.prefix}daily"
  description                  = "Mark absences and publish the daily attendance report."
  schedule_expression          = "cron(59 23 * * ? *)"
  schedule_expression_timezone = "Asia/Kolkata"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.daily_job_arn
    role_arn = aws_iam_role.scheduler[0].arn
    input    = "{}"
  }

  depends_on = [aws_iam_role_policy.scheduler_invoke]
}

resource "aws_scheduler_schedule" "weekly" {
  count                        = local.scheduler_enabled ? 1 : 0
  name                         = "${local.prefix}weekly"
  description                  = "Publish the previous ISO week's attendance analytics."
  schedule_expression          = "cron(30 0 ? * MON *)"
  schedule_expression_timezone = "Asia/Kolkata"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.weekly_job_arn
    role_arn = aws_iam_role.scheduler[0].arn
    input    = "{}"
  }

  depends_on = [aws_iam_role_policy.scheduler_invoke]
}

resource "aws_cloudwatch_metric_alarm" "daily_errors" {
  count               = var.daily_job_function_name == "" ? 0 : 1
  alarm_name          = "${local.prefix}daily-job-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    FunctionName = var.daily_job_function_name
  }
  alarm_actions = var.alerts_topic_arn == "" ? [] : [var.alerts_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "weekly_errors" {
  count               = var.weekly_job_function_name == "" ? 0 : 1
  alarm_name          = "${local.prefix}weekly-job-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    FunctionName = var.weekly_job_function_name
  }
  alarm_actions = var.alerts_topic_arn == "" ? [] : [var.alerts_topic_arn]
}
