# Terraform example values
# Copy to terraform.tfvars and customize

aws_region      = "us-east-1"
environment     = "staging"
project_name    = "imdb-scraper"
s3_bucket_name  = "datalake-imdb-656661782834-staging"
s3_prefix       = "imdb/"
ecs_task_cpu    = 256
ecs_task_memory = 512
scrape_url      = "https://www.imdb.com/pt/search/title/?title_type=video_game"
