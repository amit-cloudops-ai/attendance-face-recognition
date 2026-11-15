variable "env" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "account_id" {
  description = "AWS account ID used to scope S3 invocation permissions."
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN used by the shared data resources and encrypted DLQs."
  type        = string
}

variable "raw_bucket_name" {
  description = "Name of the shared private raw-image bucket."
  type        = string
}

variable "raw_bucket_arn" {
  description = "ARN of the shared raw-image bucket."
  type        = string
}

variable "tables" {
  description = "Names and ARNs of the DynamoDB tables consumed by Part A."
  type = object({
    employees    = object({ name = string, arn = string })
    attendance   = object({ name = string, arn = string })
    scan_results = object({ name = string, arn = string })
    config       = object({ name = string, arn = string })
    audit        = object({ name = string, arn = string })
  })
}

variable "layer_arn" {
  description = "Published attendance_common Lambda layer ARN."
  type        = string
}

variable "alerts_topic_arn" {
  description = "SNS topic ARN for Lambda and DLQ alarms."
  type        = string
}

variable "common_env" {
  description = "Common Lambda environment variables, including TZ_NAME, LOG_LEVEL and BUCKET_REPORTS."
  type        = map(string)

  validation {
    condition     = alltrue([for key in ["TZ_NAME", "LOG_LEVEL", "BUCKET_REPORTS"] : contains(keys(var.common_env), key)])
    error_message = "common_env must include TZ_NAME, LOG_LEVEL and BUCKET_REPORTS."
  }
}

variable "execution_role_boundary_arn" {
  description = "Mandatory customer-managed permissions boundary attached to all application roles."
  type        = string
}


variable "reserved_concurrency" {
  description = "Reserved concurrency for selected recognition Lambdas. Set an entry to null to use the account's unreserved pool."
  type = object({
    recognize = number
    enroll    = number
    failure   = number
  })

  validation {
    condition = alltrue([
      for value in values(var.reserved_concurrency) :
      value == null ? true : (value >= 1 && floor(value) == value)
    ])
    error_message = "Reserved concurrency values must be null or positive whole numbers."
  }
}
