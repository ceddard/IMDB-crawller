# IMDb Scraper CI/CD (AWS + GitHub Actions + Databricks)

Overview:
- Build Docker image with Playwright
- Push to AWS ECR
- Run on AWS ECS Fargate (uploads Parquet to S3)
- Optionally create/update Databricks table over S3

## Prereqs
- AWS account, ECR, ECS cluster, subnets, security group
- IAM role for ECS task with S3 PutObject
- GitHub OIDC role to assume in AWS (`AWS_ROLE_TO_ASSUME`)
- S3 bucket for output (`S3_BUCKET`)
- Databricks (optional): UC external location to S3, SQL warehouse

## Secrets (GitHub -> Settings -> Secrets and variables)
- `AWS_ACCOUNT_ID`, `AWS_REGION`, `AWS_ROLE_TO_ASSUME`
- `ECS_CLUSTER`, `ECS_TASK_DEFINITION`, `ECS_SUBNETS`, `ECS_SECURITY_GROUPS`
- `S3_BUCKET`, `S3_PREFIX` (e.g., `imdb/`)
- `SCRAPE_URL` (optional)
- Optional Databricks: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID`

## Run locally
```bash
pip install -r requirements.txt
python -m playwright install
python run.py
```

## Notes
- Respect IMDb Terms of Use; prefer official datasets where possible.
- Playwright requires Chromium; Dockerfile uses official Playwright image.
- Databricks external tables need UC external locations mapped to your S3.
