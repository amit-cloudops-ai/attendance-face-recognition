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

locals {
  function_specs = {
    presign = {
      memory_size                    = 256
      timeout                        = 5
      reserved_concurrent_executions = null
    }
    result = {
      memory_size                    = 128
      timeout                        = 3
      reserved_concurrent_executions = null
    }
    recognize = {
      memory_size                    = 512
      timeout                        = 15
      reserved_concurrent_executions = 10
    }
    enroll = {
      memory_size                    = 512
      timeout                        = 15
      reserved_concurrent_executions = 5
    }
    enroll_url = {
      memory_size                    = 256
      timeout                        = 5
      reserved_concurrent_executions = null
    }
    faces_delete = {
      memory_size                    = 256
      timeout                        = 15
      reserved_concurrent_executions = null
    }
    failure = {
      memory_size                    = 128
      timeout                        = 10
      reserved_concurrent_executions = 2
    }
  }

  lambda_environment = merge(var.common_env, {
    ENV                = var.env
    TABLE_EMPLOYEES    = var.tables.employees.name
    TABLE_ATTENDANCE   = var.tables.attendance.name
    TABLE_SCAN_RESULTS = var.tables.scan_results.name
    TABLE_CONFIG       = var.tables.config.name
    TABLE_AUDIT        = var.tables.audit.name
    BUCKET_RAW         = var.raw_bucket_name
    COLLECTION_ID      = aws_rekognition_collection.faces.collection_id
  })

  lambda_kms_permissions = {
    presign = [{
      Effect   = "Allow"
      Action   = ["kms:GenerateDataKey"]
      Resource = [var.kms_key_arn]
    }]
    recognize = [{
      Effect   = "Allow"
      Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
      Resource = [var.kms_key_arn]
    }]
    enroll = [{
      Effect   = "Allow"
      Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
      Resource = [var.kms_key_arn]
    }]
    enroll_url = [{
      Effect   = "Allow"
      Action   = ["kms:GenerateDataKey"]
      Resource = [var.kms_key_arn]
    }]
    failure = [{
      Effect   = "Allow"
      Action   = ["kms:Decrypt"]
      Resource = [var.kms_key_arn]
    }]
  }

  lambda_permissions = {
    presign = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${var.raw_bucket_arn}/captures/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = [var.tables.scan_results.arn]
      }
    ]
    result = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = [var.tables.scan_results.arn]
      }
    ]
    recognize = [
      {
        Effect   = "Allow"
        Action   = ["rekognition:DetectFaces"]
        Resource = ["*"]
      },
      {
        Effect   = "Allow"
        Action   = ["rekognition:SearchFacesByImage"]
        Resource = [aws_rekognition_collection.faces.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:DeleteObject"]
        Resource = ["${var.raw_bucket_arn}/captures/*"]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:TransactWriteItems"
        ]
        Resource = [var.tables.attendance.arn]
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:GetItem"]
        Resource = [
          var.tables.employees.arn,
          var.tables.config.arn,
          var.tables.scan_results.arn
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:TransactWriteItems"]
        Resource = [var.tables.employees.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:UpdateItem"]
        Resource = [var.tables.scan_results.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [aws_sqs_queue.dlq["recognize"].arn]
      }
    ]
    enroll = [
      {
        Effect   = "Allow"
        Action   = ["rekognition:DetectFaces"]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = [
          "rekognition:SearchFacesByImage",
          "rekognition:IndexFaces",
          "rekognition:DeleteFaces"
        ]
        Resource = [aws_rekognition_collection.faces.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:DeleteObject"]
        Resource = ["${var.raw_bucket_arn}/enroll/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = [var.tables.employees.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = [var.tables.config.arn, var.tables.scan_results.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:UpdateItem"]
        Resource = [var.tables.scan_results.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = [aws_sqs_queue.dlq["enroll"].arn]
      }
    ]
    enroll_url = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = ["${var.raw_bucket_arn}/enroll/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem"]
        Resource = [var.tables.employees.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = [var.tables.scan_results.arn]
      }
    ]
    faces_delete = [
      {
        Effect   = "Allow"
        Action   = ["rekognition:DeleteFaces"]
        Resource = [aws_rekognition_collection.faces.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:TransactWriteItems"]
        Resource = [var.tables.employees.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:TransactWriteItems"]
        Resource = [var.tables.audit.arn]
      }
    ]
    failure = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = [for queue in aws_sqs_queue.dlq : queue.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = [var.tables.scan_results.arn, var.tables.employees.arn]
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:Query", "dynamodb:Scan"]
        Resource = [
          var.tables.attendance.arn,
          "${var.tables.attendance.arn}/index/date-index"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["rekognition:SearchFacesByImage", "rekognition:DeleteFaces"]
        Resource = [aws_rekognition_collection.faces.arn]
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:DeleteObject"]
        Resource = [
          "${var.raw_bucket_arn}/captures/*",
          "${var.raw_bucket_arn}/enroll/*"
        ]
      }
    ]
  }
}

data "archive_file" "lambda" {
  for_each    = local.function_specs
  type        = "zip"
  source_dir  = "${path.module}/../../../services/recognition/${each.key}"
  output_path = "${path.module}/${each.key}.zip"
}

resource "aws_rekognition_collection" "faces" {
  collection_id = "attendance-${var.env}-faces"
}

resource "aws_sqs_queue" "failure_processor_dlq" {
  name                       = "attendance-${var.env}-failure-processor-dlq"
  kms_master_key_id          = var.kms_key_arn
  message_retention_seconds  = 1209600
  visibility_timeout_seconds = 60

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "recognition"
  }
}

resource "aws_sqs_queue" "dlq" {
  for_each = toset(["recognize", "enroll"])

  name                       = "attendance-${var.env}-${each.key}-dlq"
  kms_master_key_id          = var.kms_key_arn
  message_retention_seconds  = 1209600
  visibility_timeout_seconds = 60
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.failure_processor_dlq.arn
    maxReceiveCount     = 5
  })

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "recognition"
  }
}

resource "aws_sqs_queue_redrive_allow_policy" "failure_processor" {
  queue_url = aws_sqs_queue.failure_processor_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [for queue in aws_sqs_queue.dlq : queue.arn]
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.function_specs

  name              = "/aws/lambda/attendance-${var.env}-${replace(each.key, "_", "-")}"
  retention_in_days = 30

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "recognition"
  }
}

resource "aws_iam_role" "lambda" {
  for_each = local.function_specs

  name                 = "attendance-${var.env}-${replace(each.key, "_", "-")}"
  assume_role_policy   = data.aws_iam_policy_document.lambda_assume_role.json
  permissions_boundary = var.execution_role_boundary_arn

  tags = {
    Project     = "attendance"
    Environment = var.env
    Component   = "recognition"
  }
}

resource "aws_iam_role_policy" "lambda" {
  for_each = local.function_specs

  name = "attendance-${var.env}-${replace(each.key, "_", "-")}-permissions"
  role = aws_iam_role.lambda[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.lambda_permissions[each.key], lookup(local.lambda_kms_permissions, each.key, []), [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["${aws_cloudwatch_log_group.lambda[each.key].arn}:*"]
      },
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
    Component   = "recognition"
  }
}

resource "aws_lambda_function_event_invoke_config" "dlq" {
  for_each = toset(["recognize", "enroll"])

  function_name                = aws_lambda_function.lambda[each.key].function_name
  maximum_event_age_in_seconds = 600
  maximum_retry_attempts       = 2

  destination_config {
    on_failure {
      destination = aws_sqs_queue.dlq[each.key].arn
    }
  }
}

resource "aws_lambda_event_source_mapping" "failure" {
  for_each = aws_sqs_queue.dlq

  event_source_arn                   = each.value.arn
  function_name                      = aws_lambda_function.lambda["failure"].arn
  batch_size                         = 1
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_batching_window_in_seconds = 0

  depends_on = [aws_iam_role_policy.lambda]
}

resource "aws_lambda_permission" "s3" {
  for_each = toset(["recognize", "enroll"])

  statement_id   = "AllowS3Invoke${title(each.key)}"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.lambda[each.key].function_name
  principal      = "s3.amazonaws.com"
  source_arn     = var.raw_bucket_arn
  source_account = var.account_id
}

resource "aws_s3_bucket_notification" "raw" {
  bucket = var.raw_bucket_name

  lambda_function {
    lambda_function_arn = aws_lambda_function.lambda["recognize"].arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "captures/"
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.lambda["enroll"].arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "enroll/"
  }

  depends_on = [aws_lambda_permission.s3]
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = local.function_specs

  alarm_name          = "attendance-${var.env}-${replace(each.key, "_", "-")}-errors"
  alarm_description   = "One or more invocations of the recognition Lambda failed."
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
  alarm_description   = "The recognition Lambda was throttled."
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

resource "aws_cloudwatch_metric_alarm" "recognize_p95" {
  alarm_name          = "attendance-${var.env}-recognize-p95-duration"
  alarm_description   = "Recognition p95 duration exceeded 2500 milliseconds."
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  extended_statistic  = "p95"
  period              = 60
  evaluation_periods  = 1
  threshold           = 2500
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alerts_topic_arn]

  dimensions = {
    FunctionName = aws_lambda_function.lambda["recognize"].function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  for_each = aws_sqs_queue.dlq

  alarm_name          = "attendance-${var.env}-${each.key}-dlq-depth"
  alarm_description   = "Messages are waiting in the recognition dead-letter queue."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alerts_topic_arn]

  dimensions = {
    QueueName = each.value.name
  }
}


resource "aws_cloudwatch_metric_alarm" "failure_processor_dlq_depth" {
  alarm_name          = "attendance-${var.env}-failure-processor-dlq-depth"
  alarm_description   = "Failure events could not be converted into terminal scan or enrollment results."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alerts_topic_arn]

  dimensions = {
    QueueName = aws_sqs_queue.failure_processor_dlq.name
  }
}
