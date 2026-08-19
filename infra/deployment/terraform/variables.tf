variable "environment" {
  description = "Deployment environment."
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "aws_region" {
  description = "AWS region. CloudFront certificates require us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "baladiguard"
}

variable "owner" {
  description = "Operational owner recorded on every resource."
  type        = string
  default     = "Mahmoud"
}

variable "route53_zone_id" {
  description = "Public Route 53 hosted zone id for both aliases."
  type        = string
}

variable "api_domain_name" {
  description = "API hostname, for example api.staging.example.com."
  type        = string
}

variable "admin_domain_name" {
  description = "Admin hostname, for example admin.staging.example.com."
  type        = string
}

variable "runtime_secret_arn" {
  description = "Secrets Manager JSON secret containing the runtime keys listed below."
  type        = string
  sensitive   = true
}

variable "runtime_secret_keys" {
  description = "JSON keys injected from runtime_secret_arn without exposing values to Terraform."
  type        = set(string)
  default = [
    "SECRET_KEY",
    "CITIZEN_APP_BASE_URL",
    "CORS_ALLOWED_ORIGINS",
    "LOCATION_PLACE_INDEX_NAME",
    "SES_FROM_EMAIL",
    "SES_CONFIGURATION_SET",
    "SNS_SMS_SENDER_ID",
    "RATE_LIMIT_SMOKE_BYPASS_TOKEN",
  ]
}

variable "backend_image" {
  description = "Immutable ECR image reference including sha256 digest."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.backend_image))
    error_message = "backend_image must be an immutable image digest, not a mutable tag."
  }
}

variable "app_version" {
  description = "Auditable release label (tag or commit SHA)."
  type        = string
}

variable "api_desired_count" {
  type    = number
  default = 1
  validation {
    condition     = var.api_desired_count >= 1
    error_message = "At least one API task is required."
  }
}

variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "worker_cpu" {
  type    = number
  default = 512
}

variable "worker_memory" {
  type    = number
  default = 1024
}

variable "redaction_cpu" {
  type    = number
  default = 1024
}

variable "redaction_memory" {
  type    = number
  default = 2048
}

variable "log_retention_days" {
  type    = number
  default = 30
}
