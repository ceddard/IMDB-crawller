# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = var.project_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-cluster"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-logs"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "scraper" {
  family                   = var.project_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  task_role_arn            = aws_iam_role.ecs_task.arn
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name      = "app"
    image     = "${aws_ecr_repository.scraper.repository_url}:latest"
    essential = true

    environment = [
      {
        name  = "SCRAPE_URL"
        value = var.scrape_url
      },
      {
        name  = "AWS_REGION"
        value = var.aws_region
      },
      {
        name  = "S3_BUCKET"
        value = aws_s3_bucket.landing_zone.id
      },
      {
        name  = "S3_PREFIX"
        value = var.s3_prefix
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = {
    Name = "${var.project_name}-task-def"
  }
}

# Default VPC and Subnets (use existing)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security Group for ECS Task
resource "aws_security_group" "ecs_task" {
  name        = "${var.project_name}-ecs-task-sg"
  description = "Security group for ECS Fargate task"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic (for IMDb and S3)"
  }

  tags = {
    Name = "${var.project_name}-ecs-sg"
  }
}
