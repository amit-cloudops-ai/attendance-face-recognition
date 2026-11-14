output "api_routes" {
  description = "HTTP API route contracts exported by the data module."
  value = {
    "GET /api/admin/employees" = {
      function_name = aws_lambda_function.lambda["employees"].function_name
      invoke_arn    = aws_lambda_function.lambda["employees"].invoke_arn
      group         = "admin"
    }
    "GET /api/admin/employees/{employee_id}" = {
      function_name = aws_lambda_function.lambda["employees"].function_name
      invoke_arn    = aws_lambda_function.lambda["employees"].invoke_arn
      group         = "admin"
    }
    "POST /api/admin/employees" = {
      function_name = aws_lambda_function.lambda["employees"].function_name
      invoke_arn    = aws_lambda_function.lambda["employees"].invoke_arn
      group         = "admin"
    }
    "DELETE /api/admin/employees/{employee_id}" = {
      function_name = aws_lambda_function.lambda["employees"].function_name
      invoke_arn    = aws_lambda_function.lambda["employees"].invoke_arn
      group         = "admin"
    }
    "GET /api/admin/attendance" = {
      function_name = aws_lambda_function.lambda["attendance_query"].function_name
      invoke_arn    = aws_lambda_function.lambda["attendance_query"].invoke_arn
      group         = "admin"
    }
    "GET /api/admin/reports" = {
      function_name = aws_lambda_function.lambda["reports"].function_name
      invoke_arn    = aws_lambda_function.lambda["reports"].invoke_arn
      group         = "admin"
    }
    "POST /api/admin/attendance/override" = {
      function_name = aws_lambda_function.lambda["override"].function_name
      invoke_arn    = aws_lambda_function.lambda["override"].invoke_arn
      group         = "admin"
    }
    "GET /api/admin/settings" = {
      function_name = aws_lambda_function.lambda["settings"].function_name
      invoke_arn    = aws_lambda_function.lambda["settings"].invoke_arn
      group         = "admin"
    }
    "PUT /api/admin/settings" = {
      function_name = aws_lambda_function.lambda["settings"].function_name
      invoke_arn    = aws_lambda_function.lambda["settings"].invoke_arn
      group         = "admin"
    }
  }
}

output "tables" {
  description = "DynamoDB table names and ARNs consumed by the recognition module and access layer."
  value = {
    employees = {
      name = aws_dynamodb_table.employees.name
      arn  = aws_dynamodb_table.employees.arn
    }
    attendance = {
      name = aws_dynamodb_table.attendance.name
      arn  = aws_dynamodb_table.attendance.arn
    }
    scan_results = {
      name = aws_dynamodb_table.scan_results.name
      arn  = aws_dynamodb_table.scan_results.arn
    }
    config = {
      name = aws_dynamodb_table.config.name
      arn  = aws_dynamodb_table.config.arn
    }
    audit = {
      name = aws_dynamodb_table.audit.name
      arn  = aws_dynamodb_table.audit.arn
    }
  }
}
