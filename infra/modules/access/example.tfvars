# Example only. Real invoke ARNs and function names come from the Part A and Part B module outputs.
env = "dev"

route_map = {
  "POST /api/kiosk/upload-url"                = { invoke_arn = "REPLACE", function_name = "attendance-dev-presign" }
  "GET /api/kiosk/result/{request_id}"        = { invoke_arn = "REPLACE", function_name = "attendance-dev-result" }
  "POST /api/admin/employees"                 = { invoke_arn = "REPLACE", function_name = "attendance-dev-employees" }
  "GET /api/admin/employees"                  = { invoke_arn = "REPLACE", function_name = "attendance-dev-employees" }
  "GET /api/admin/attendance"                 = { invoke_arn = "REPLACE", function_name = "attendance-dev-attendance" }
  "GET /api/admin/reports"                    = { invoke_arn = "REPLACE", function_name = "attendance-dev-reports" }
  "POST /api/admin/employees/{id}/enroll-url" = { invoke_arn = "REPLACE", function_name = "attendance-dev-enroll" }
  "DELETE /api/admin/employees/{id}/faces"    = { invoke_arn = "REPLACE", function_name = "attendance-dev-delete-faces" }
}

# extra_origins = ["http://localhost:8000"]  # local testing only
