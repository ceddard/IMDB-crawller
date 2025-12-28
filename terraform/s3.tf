# S3 Bucket for Landing Zone
resource "aws_s3_bucket" "landing_zone" {
  bucket = var.s3_bucket_name

  tags = {
    Name = "${var.project_name}-landing-zone"
  }
}

resource "aws_s3_bucket_versioning" "landing_zone" {
  count  = var.enable_s3_versioning ? 1 : 0
  bucket = aws_s3_bucket.landing_zone.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "landing_zone" {
  bucket = aws_s3_bucket.landing_zone.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = var.s3_lifecycle_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "landing_zone" {
  bucket = aws_s3_bucket.landing_zone.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
