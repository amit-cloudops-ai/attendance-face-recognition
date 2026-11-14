data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "scheduler_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

locals {
  function_specs = {
    employees = {
      memory_size                    = 256
      timeout                        = 10
      reserved_concurrent_executions = null
    }
    attendance_query = {
      memory_size                    = 256
      timeout                        = 10
      reserved_concurrent_executions = null
    }
    daily_job = {
      memory_size                    = 512
      timeout                        = 60
      reserved_concurrent_executions = 1
    }
    weekly_job = {
      memory_size                    = 512
      timeout                        = 120
      reserved_concurrent_executions = 1
    }
    reports = {
      memory_size                    = 256
      timeout                        = 10
      reserved_concurrent_executions = null
    }
  }

  lambda_environment = merge(var.common_env, {
    ENV                = var.env
    TABLE_EMPLOYEES    = aws_dynamodb_table.employees.name
    TABLE_ATTENDANCE   = aws_dynamodb_table.attendance.name
    TABLE_SCAN_RESULTS = aws_dynamodb_table.scan_results.name
    TABLE_CONFIG       = aws_dynamodb_table.config.name
    TABLE_AUDIT        = aws_dynamodb_table.audit.name
    BUCKET_RAW         = var.raw_bucket_name
    BUCKET_REPORTS     = var.reports_bucket_name
    COLLECTION_ID      = var.collection_id
    ALERTS_TOPIC_ARN   = var.alerts_topic_arn
  })

  lambda_permissions = {
    employees = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Scan"
        ]
        Resource = [aws_dynamodb_table.employees.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = [aws_dynamodb_table.audit.arn]
      }
    ]
    attendance_query = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:Query"]
        Resource = [
          aws_dynamodb_table.attendance.arn,
          "${aws_dynamodb_table.attendance.arn}/index/date-index"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:Scan"]
        Resource = [aws_dynamodb_table.employees.arn]
      }
    ]
    daily_job = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:Scan"]
        Resource = [aws_dynamodb_table.employees.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:Query"]
        Resource = [
          aws_dynamodb_table.attendance.arn,
          "${aws_dynamodb_table.attendance.arn}/index/date-index"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = [aws_dynamodb_table.attendance.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = [aws_dynamodb_table.config.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${var.reports_bucket_arn}/reports/daily/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [var.alerts_topic_arn]
      }
    ]
    weekly_job = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:Scan"]
        Resource = [aws_dynamodb_table.employees.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:Query"]
        Resource = [
          aws_dynamodb_table.attendance.arn,
          "${aws_dynamodb_table.attendance.arn}/index/date-index"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = [aws_dynamodb_table.config.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${var.reports_bucket_arn}/reports/weekly/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [var.alerts_topic_arn]
      }
    ]
    reports = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${var.reports_bucket_arn}/reports/*"]
      }
    ]
  }
}

resource "aws_dynamodb_table" "employees" {
  name                        = "attendance-${var.env}-employees"
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

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "data"
  }
}

resource "aws_dynamodb_table" "attendance" {
  name                        = "attendance-${var.env}-attendance"
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

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "data"
  }
}

resource "aws_dynamodb_table" "scan_results" {
  name                        = "attendance-${var.env}-scan-results"
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

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "data"
  }
}

resource "aws_dynamodb_table" "config" {
  name                        = "attendance-${var.env}-config"
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

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "data"
  }
}

resource "aws_dynamodb_table" "audit" {
  name                        = "attendance-${var.env}-audit"
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

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "data"
  }
}

data "archive_file" "lambda" {
  for_each    = local.function_specs
  type        = "zip"
  source_dir  = "${path.module}/../../../services/data/${each.key}"
  output_path = "${path.module}/${each.key}.zip"
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.function_specs

  name              = "/aws/lambda/attendance-${var.env}-${replace(each.key, "_", "-")}"
  retention_in_days = 30

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "data"
  }
}

resource "aws_iam_role" "lambda" {
  for_each = local.function_specs

  name               = "attendance-${var.env}-${replace(each.key, "_", "-")}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "data"
  }
}

resource "aws_iam_role_policy" "lambda" {
  for_each = local.function_specs

  name = "attendance-${var.env}-${replace(each.key, "_", "-")}-permissions"
  role = aws_iam_role.lambda[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.lambda_permissions[each.key], [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["${aws_cloudwatch_log_group.lambda[each.key].arn}:*"]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = [var.kms_key_arn]
      }
    ])
  })
}

resource "aws_lambda_function" "lambda" {
  for_each = local.function_specs

  function_name    = "attendance-${var.env}-${replace(each.key, "_", "-")}"
  role             = aws_iam_role.lambda[each.key].arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.lambda[each.key].output_path
  source_code_hash = data.archive_file.lambda[each.key].output_base64sha256
  memory_size      = each.value.memory_size
  timeout          = each.value.timeout
  publish          = true

  reserved_concurrent_executions = each.value.reserved_concurrent_executions
  layers                         = [var.layer_arn]

  environment {
    variables = local.lambda_environment
  }

  depends_on = [aws_iam_role_policy.lambda]

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "data"
  }
}

resource "aws_iam_role" "scheduler" {
  for_each = toset(["daily_job", "weekly_job"])

  name               = "attendance-${var.env}-${replace(each.key, "_", "-")}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume_role.json
}

resource "aws_iam_role_policy" "scheduler" {
  for_each = toset(["daily_job", "weekly_job"])

  name = "attendance-${var.env}-${replace(each.key, "_", "-")}-invoke"
  role = aws_iam_role.scheduler[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = [aws_lambda_function.lambda[each.key].arn]
    }]
  })
}

resource "aws_scheduler_schedule" "jobs" {
  for_each = toset(["daily_job", "weekly_job"])

  name                         = "attendance-${var.env}-${replace(each.key, "_", "-")}"
  description                  = "Run the attendance ${replace(each.key, "_", " ")} in Asia/Kolkata."
  schedule_expression          = each.key == "daily_job" ? "cron(59 23 * * ? *)" : "cron(30 0 ? * MON *)"
  schedule_expression_timezone = "Asia/Kolkata"
  state                        = "ENABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.lambda[each.key].arn
    role_arn = aws_iam_role.scheduler[each.key].arn
    input    = "{}"

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }

  depends_on = [aws_iam_role_policy.scheduler]
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = local.function_specs

  alarm_name          = "attendance-${var.env}-${replace(each.key, "_", "-")}-errors"
  alarm_description   = "One or more invocations of the data Lambda failed."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alerts_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.lambda[each.key].function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each = local.function_specs

  alarm_name          = "attendance-${var.env}-${replace(each.key, "_", "-")}-throttles"
  alarm_description   = "The data Lambda was throttled."
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alerts_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.lambda[each.key].function_name
  }
}
