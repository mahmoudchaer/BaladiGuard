output "state_bucket" {
  value = aws_s3_bucket.state.bucket
}

output "lock_table" {
  value = aws_dynamodb_table.locks.name
}

output "deployment_role_arns" {
  value = { for environment, role in aws_iam_role.github_deploy : environment => role.arn }
}

output "ecr_repository_urls" {
  value = { for environment, repository in aws_ecr_repository.backend : environment => repository.repository_url }
}
