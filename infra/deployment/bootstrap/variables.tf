variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "github_repository" {
  description = "GitHub owner/repository allowed to request deployment credentials."
  type        = string
}

variable "github_oidc_provider_arn" {
  description = "ARN of an existing GitHub OIDC provider in this account. AWS allows only one provider per URL; set this if the account already has one. Leave empty to create the provider here."
  type        = string
  default     = ""
}

variable "state_bucket_name" {
  type = string
}

variable "lock_table_name" {
  type    = string
  default = "baladiguard-terraform-locks"
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID for DNS record management."
  type        = string
}
