output "tables" {
  description = "DynamoDB table names and ARNs for the other modules."
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

output "api_routes" {
  description = "Admin routes consumed by the access module."
  value       = local.api_routes
}

output "daily_job_arn" {
  value = var.daily_job_arn
}

output "weekly_job_arn" {
  value = var.weekly_job_arn
}
