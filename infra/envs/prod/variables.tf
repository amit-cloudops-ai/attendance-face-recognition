variable "env" {
  description = "Deployment environment for this root."
  type        = string
  default     = "prod"

  validation {
    condition     = var.env == "prod"
    error_message = "infra/envs/prod only supports env=prod."
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

variable "callback_urls" {
  description = "Exact Cognito Hosted UI callback URLs. Start with localhost for initial provisioning, then add the CloudFront site URL."
  type        = list(string)

  validation {
    condition     = length(var.callback_urls) > 0
    error_message = "At least one Cognito callback URL is required."
  }
}

variable "logout_urls" {
  description = "Exact Cognito Hosted UI logout URLs."
  type        = list(string)

  validation {
    condition     = length(var.logout_urls) > 0
    error_message = "At least one Cognito logout URL is required."
  }
}

variable "allowed_origins" {
  description = "Exact browser origins allowed for raw S3 presigned POST uploads and API CORS."
  type        = list(string)

  validation {
    condition     = length(var.allowed_origins) > 0
    error_message = "At least one browser origin is required."
  }
}
