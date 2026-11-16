variable "env" {
  description = "Environment name (dev or prod). Resources are prefixed attendance-{env}-."
  type        = string
}

variable "route_map" {
  description = "Route map from Parts A and B. Key is the API route key, for example \"POST /api/kiosk/upload-url\"."
  type = map(object({
    invoke_arn    = string
    function_name = string
  }))
}

variable "kms_key_arn" {
  description = "Optional KMS key for the web bucket. Its key policy must allow cloudfront.amazonaws.com to decrypt. Null uses S3-managed encryption."
  type        = string
  default     = null
}

variable "extra_origins" {
  description = "Extra browser origins for CORS and Cognito callbacks, for example http://localhost:8000 for local testing."
  type        = list(string)
  default     = []
}

variable "throttle_rate_limit" {
  type    = number
  default = 20
}

variable "throttle_burst_limit" {
  type    = number
  default = 40
}
