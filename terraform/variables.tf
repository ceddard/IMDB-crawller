variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "imdb-scraper"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for landing zone"
  type        = string
}

variable "s3_prefix" {
  description = "S3 prefix for JSONL files"
  type        = string
  default     = "imdb/"
}

variable "ecs_task_cpu" {
  description = "ECS task CPU units (256 = 0.25 vCPU)"
  type        = number
  default     = 256
}

variable "ecs_task_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 512
}

variable "scrape_url" {
  description = "Default IMDb URL to scrape"
  type        = string
  default     = "https://www.imdb.com/pt/search/title/?title_type=video_game"
}

variable "enable_s3_versioning" {
  description = "Enable S3 bucket versioning"
  type        = bool
  default     = true
}

variable "s3_lifecycle_days" {
  description = "Days before transitioning to cheaper storage"
  type        = number
  default     = 90
}
