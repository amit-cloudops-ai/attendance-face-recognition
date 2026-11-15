variable "env" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be dev or prod."
  }
}

variable "account_id" {
  description = "12-digit AWS account ID used in globally unique bucket names."
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.account_id))
    error_message = "account_id must contain exactly 12 digits."
  }
}

variable "alert_email" {
  description = "Email address subscribed to the attendance alerts topic."
  type        = string
}

variable "raw_upload_origins" {
  description = "Exact browser origins permitted to POST short-lived kiosk/enrollment presigned uploads."
  type        = list(string)

  validation {
    condition     = length(var.raw_upload_origins) > 0
    error_message = "At least one raw upload origin is required."
  }
}
