variable "env" {
  description = "Deployment environment for this root."
  type        = string
  default     = "dev"

  validation {
    condition     = var.env == "dev"
    error_message = "infra/envs/dev only supports env=dev."
  }
}

variable "account_id" {
  description = "12-digit AWS account ID."
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.account_id))
    error_message = "account_id must contain exactly 12 digits."
  }
}

variable "alert_email" {
  description = "Email address for SNS and budget notifications."
  type        = string
}
