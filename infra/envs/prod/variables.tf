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

variable "execution_role_boundary_arn" {
  description = "Pre-created us-east-1 customer-managed IAM permissions boundary ARN for prod execution roles."
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::\\d{12}:policy/attendance-prod-execution-boundary$", var.execution_role_boundary_arn))
    error_message = "execution_role_boundary_arn must be the pre-created attendance-prod-execution-boundary policy in this AWS account."
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
