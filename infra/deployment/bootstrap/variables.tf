variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "github_repository" {
  description = "GitHub owner/repository allowed to request deployment credentials."
  type        = string
}

variable "state_bucket_name" {
  type = string
}

variable "lock_table_name" {
  type    = string
  default = "baladiguard-terraform-locks"
}
