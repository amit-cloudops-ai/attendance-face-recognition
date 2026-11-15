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

variable "api_id" {
  description = "Pre-created, owner-approved API Gateway HTTP API ID imported into this environment's Terraform state."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{10}$", var.api_id))
    error_message = "api_id must be exactly 10 lowercase alphanumeric characters."
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
    condition     = can(regex("^arn:aws:iam::\\d{12}:policy/attendance-dev-execution-boundary$", var.execution_role_boundary_arn))
    error_message = "execution_role_boundary_arn must be the pre-created attendance-dev-execution-boundary policy in this AWS account."
  }
}

variable "lambda_reserved_concurrency" {
  description = "Per-environment Lambda reserved concurrency. Set individual functions to null when the account quota cannot support reservations."
  type = object({
    recognize = number
    enroll    = number
    failure   = number
    daily     = number
    weekly    = number
  })
  default = {
    recognize = 10
    enroll    = 5
    failure   = 2
    daily     = 1
    weekly    = 1
  }

  validation {
    condition = alltrue([
      for value in values(var.lambda_reserved_concurrency) :
      value == null ? true : (value >= 1 && floor(value) == value)
    ])
    error_message = "Lambda reserved concurrency values must be null or positive whole numbers."
  }
}
