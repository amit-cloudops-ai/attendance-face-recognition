variable "env" {
  description = "Deployment environment: dev or prod."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "kms_key_arn" {
  description = "Shared KMS key ARN used for DynamoDB encryption."
  type        = string
}

variable "daily_job_arn" {
  description = "Invoke ARN for the daily attendance Lambda."
  type        = string
  default     = ""
}

variable "weekly_job_arn" {
  description = "Invoke ARN for the weekly attendance Lambda."
  type        = string
  default     = ""
}

variable "daily_job_function_name" {
  description = "Name of the daily attendance Lambda, used by the alarm."
  type        = string
  default     = ""
}

variable "weekly_job_function_name" {
  description = "Name of the weekly attendance Lambda, used by the alarm."
  type        = string
  default     = ""
}

variable "alerts_topic_arn" {
  description = "SNS topic ARN for job failure notifications."
  type        = string
  default     = ""
}

variable "api_lambdas" {
  description = "Function names and invoke ARNs for the Part B API Lambdas."
  type = map(object({
    function_name = string
    invoke_arn    = string
  }))
  default = {}
}
