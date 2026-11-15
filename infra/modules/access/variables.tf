variable "env" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "region" {
  description = "Canonical AWS region supplied by the environment root."
  type        = string
}

variable "account_id" {
  description = "12-digit AWS account ID used for the Cognito domain and CloudFront policy."
  type        = string
}

variable "raw_bucket_name" {
  description = "Private raw biometric bucket name used by browser upload configuration."
  type        = string
}

variable "web_bucket_name" {
  description = "Private static web bucket name."
  type        = string
}

variable "web_bucket_arn" {
  description = "Private static web bucket ARN."
  type        = string
}

variable "web_bucket_regional_domain_name" {
  description = "Regional S3 REST endpoint used as the CloudFront web origin."
  type        = string
}

variable "api_routes" {
  description = "Frozen API route map exported by the recognition and data modules."
  type = map(object({
    function_name = string
    invoke_arn    = string
    group         = string
  }))
}

variable "callback_urls" {
  description = "Exact Cognito Hosted UI callback URLs. Add the CloudFront site URL after the first infrastructure plan."
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
  description = "Additional browser origins allowed by API Gateway CORS; CloudFront web/API traffic is same-origin."
  type        = list(string)
}

variable "kms_key_id" {
  description = "Foundation customer-managed KMS key ID whose final key policy is attached after the CloudFront distribution is created."
  type        = string
}
