variable "account_id" {
  description = "Expected 12-digit AWS account ID for this billing root."
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.account_id))
    error_message = "account_id must contain exactly 12 digits."
  }
}

variable "alert_email" {
  description = "Email address for the dev and prod AWS Budget notifications."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email must be a valid email address."
  }
}
