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

variable "callback_urls" {
  description = "Exact Cognito Hosted UI callback URLs. Add the CloudFront site URL after the first apply."
  type        = list(string)
  default     = ["http://localhost:8000/callback.html"]
}

variable "logout_urls" {
  description = "Exact Cognito Hosted UI logout URLs."
  type        = list(string)
  default     = ["http://localhost:8000/"]
}

variable "allowed_origins" {
  description = "Additional browser origins for local API development. CloudFront web/API requests are same-origin."
  type        = list(string)
  default     = ["http://localhost:8000"]
}

variable "execution_role_boundary_arn" {
  description = "Pre-created us-east-1 customer-managed IAM permissions boundary ARN for dev execution roles."
  type        = string

  validation {
    condition     = var.execution_role_boundary_arn == format("arn:aws:iam::%s:policy/attendance-dev-execution-boundary", var.account_id)
    error_message = "execution_role_boundary_arn must be the pre-created attendance-dev-execution-boundary policy in this AWS account."
  }
}
