output "aws_account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS Region"
  value       = var.aws_region
}

output "s3_bucket_name" {
  description = "S3 bucket name for landing zone"
  value       = aws_s3_bucket.landing_zone.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.landing_zone.arn
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.scraper.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ECS cluster ARN"
  value       = aws_ecs_cluster.main.arn
}

output "ecs_task_definition" {
  description = "ECS task definition family"
  value       = aws_ecs_task_definition.scraper.family
}

output "ecs_task_definition_arn" {
  description = "ECS task definition ARN"
  value       = aws_ecs_task_definition.scraper.arn
}

output "ecs_security_group_id" {
  description = "Security group ID for ECS tasks"
  value       = aws_security_group.ecs_task.id
}

output "ecs_subnets" {
  description = "Subnet IDs for ECS tasks (comma-separated for GitHub secrets)"
  value       = join(",", data.aws_subnets.default.ids)
}

output "ecs_task_role_arn" {
  description = "IAM role ARN for ECS task"
  value       = aws_iam_role.ecs_task.arn
}

output "ecs_execution_role_arn" {
  description = "IAM role ARN for ECS task execution"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.ecs.name
}

# Summary for GitHub Secrets
output "github_secrets_summary" {
  description = "Summary of values for GitHub Secrets"
  value = {
    AWS_ACCOUNT_ID         = data.aws_caller_identity.current.account_id
    AWS_REGION             = var.aws_region
    ECS_CLUSTER            = aws_ecs_cluster.main.name
    ECS_TASK_DEFINITION    = aws_ecs_task_definition.scraper.family
    ECS_SUBNETS            = join(",", data.aws_subnets.default.ids)
    ECS_SECURITY_GROUPS    = aws_security_group.ecs_task.id
    S3_BUCKET              = aws_s3_bucket.landing_zone.id
    S3_PREFIX              = var.s3_prefix
    SCRAPE_URL             = var.scrape_url
  }
}
