terraform {
  required_version = ">= 1.6"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "datalake-imdb-656661782834-staging"
    key    = "terraform/state/imdb-scraper.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "imdb-scraper"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
