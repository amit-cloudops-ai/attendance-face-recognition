output "api_routes" {
  description = "HTTP API route contracts exported by the recognition module."
  value = {
    "POST /api/kiosk/upload-url" = {
      function_name = aws_lambda_function.lambda["presign"].function_name
      invoke_arn    = aws_lambda_function.lambda["presign"].invoke_arn
      group         = "kiosk,admin"
    }
    "GET /api/kiosk/result/{request_id}" = {
      function_name = aws_lambda_function.lambda["result"].function_name
      invoke_arn    = aws_lambda_function.lambda["result"].invoke_arn
      group         = "kiosk,admin"
    }
    "POST /api/admin/employees/{employee_id}/enroll-url" = {
      function_name = aws_lambda_function.lambda["enroll_url"].function_name
      invoke_arn    = aws_lambda_function.lambda["enroll_url"].invoke_arn
      group         = "admin"
    }
    "DELETE /api/admin/employees/{employee_id}/faces" = {
      function_name = aws_lambda_function.lambda["faces_delete"].function_name
      invoke_arn    = aws_lambda_function.lambda["faces_delete"].invoke_arn
      group         = "admin"
    }
  }
}

output "collection_id" {
  description = "Amazon Rekognition collection ID."
  value       = aws_rekognition_collection.faces.collection_id
}

output "recognize_function_name" {
  description = "Name of the S3-triggered recognition worker."
  value       = aws_lambda_function.lambda["recognize"].function_name
}
