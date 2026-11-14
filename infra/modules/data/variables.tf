variable "env" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "account_id" {
  description = "12-digit AWS account ID used to constrain the Scheduler service trust policy."
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.account_id))
    error_message = "account_id must contain exactly 12 digits."
  }
}

variable "kms_key_arn" {
  description = "KMS key ARN for DynamoDB and report objects."
  type        = string
}

variable "raw_bucket_name" {
  description = "Shared private raw-image bucket name, exposed to every Lambda as BUCKET_RAW."
  type        = string
}

variable "reports_bucket_name" {
  description = "Shared private report bucket name."
  type        = string
}

variable "reports_bucket_arn" {
  description = "Shared report bucket ARN."
  type        = string
}

variable "collection_id" {
  description = "Rekognition collection ID created by the recognition module."
  type        = string
}

variable "layer_arn" {
  description = "Published attendance_common Lambda layer ARN."
  type        = string
}

variable "alerts_topic_arn" {
  description = "SNS topic ARN for scheduled-job failure notifications and alarms."
  type        = string
}

variable "common_env" {
  description = "Additional shared Lambda environment variables."
  type        = map(string)

  validation {
    condition     = alltrue([for key in ["TZ_NAME", "LOG_LEVEL"] : contains(keys(var.common_env), key)])
    error_message = "common_env must include TZ_NAME and LOG_LEVEL."
  }
}

variable "execution_role_boundary_arn" {
  description = "Mandatory customer-managed permissions boundary attached to all application roles."
  type        = string
}
