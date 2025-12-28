# AWS Setup Passo-a-Passo

## 1. Pré-requisitos

- [ ] Conta AWS com permissões de admin ou suficientes
- [ ] AWS CLI instalado e configurado
- [ ] Repositório GitHub com Actions habilitadas
- [ ] Databricks workspace (opcional, para a última etapa)

---

## 2. Criar S3 Bucket (Landing Zone)

```bash
export AWS_REGION="us-east-1"  # ou sua região
export BUCKET_NAME="my-imdb-datalake"

aws s3api create-bucket \
  --bucket $BUCKET_NAME \
  --region $AWS_REGION

# Ativar versionamento (recomendado)
aws s3api put-bucket-versioning \
  --bucket $BUCKET_NAME \
  --versioning-configuration Status=Enabled
```

---

## 3. Criar ECR Repository

```bash
export ECR_REPO_NAME="imdb-scraper"

aws ecr create-repository \
  --repository-name $ECR_REPO_NAME \
  --region $AWS_REGION

# Output: copiar o `repositoryUri`
```

---

## 4. Criar IAM Role para ECS Task

### 4.1 Criar Role

```bash
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Criar role com trust policy para ECS
aws iam create-role \
  --role-name ecsTaskRole-imdb-scraper \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }]
  }'

# Criar e atribuir policy inline
aws iam put-role-policy \
  --role-name ecsTaskRole-imdb-scraper \
  --policy-name S3AndCloudWatch \
  --policy-document file://aws/iam-task-role-policy.json
```

**ANTES**: Edite `aws/iam-task-role-policy.json`:
- Substitua `YOUR_BUCKET_NAME` pelo seu bucket
- Substitua `YOUR_REGION`, `YOUR_AWS_ACCOUNT_ID`

### 4.2 Criar Role de Execução (para CloudWatch Logs)

```bash
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }]
  }'

# Atribuir policy padrão AWS
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

---

## 5. Criar IAM Role para GitHub Actions (OIDC)

### 5.1 Adicionar OIDC Provider (uma vez por conta)

```bash
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"
```

### 5.2 Criar Role GitHub

```bash
export GITHUB_ORG="seu-username-ou-org"
export GITHUB_REPO="imdb-dataset"

# Edite aws/iam-github-oidc-trust.json:
# - Substitua YOUR_GITHUB_ORG e imdb-dataset
# - Substitua YOUR_AWS_ACCOUNT_ID

aws iam create-role \
  --role-name GitHubActionsRole-imdb-scraper \
  --assume-role-policy-document file://aws/iam-github-oidc-trust.json

# Edite aws/iam-github-actions-policy.json:
# - Substitua YOUR_AWS_ACCOUNT_ID, YOUR_REGION, imdb-scraper

aws iam put-role-policy \
  --role-name GitHubActionsRole-imdb-scraper \
  --policy-name ECRAndECS \
  --policy-document file://aws/iam-github-actions-policy.json
```

---

## 6. Setup ECS Cluster (se não existir)

```bash
export CLUSTER_NAME="imdb"

# Criar cluster (somente EC2 capacity provider, Fargate não precisa)
aws ecs create-cluster \
  --cluster-name $CLUSTER_NAME \
  --region $AWS_REGION

# Nota: Fargate não requer instâncias EC2
```

---

## 7. Registrar ECS Task Definition

```bash
# Edite aws/ecs-task-definition.json:
# - Substitua YOUR_AWS_ACCOUNT_ID, YOUR_REGION
# - Substitua YOUR_BUCKET_NAME e caminho S3

aws ecs register-task-definition \
  --cli-input-json file://aws/ecs-task-definition.json \
  --region $AWS_REGION

# Verificar
aws ecs describe-task-definition \
  --task-definition imdb-scraper \
  --region $AWS_REGION
```

---

## 8. Criar VPC/Subnets/Security Group para Fargate (se necessário)

```bash
# Usar VPC padrão ou VPC existente
# Exemplo: obter VPC padrão
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' \
  --output text)

# Obter subnets padrão
SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].SubnetId' \
  --output text)

# Criar security group
SG_ID=$(aws ec2 create-security-group \
  --group-name ecs-imdb-scraper \
  --description "ECS Fargate para IMDb scraper" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text)

# Permitir saída (para acessar IMDb e S3)
aws ec2 authorize-security-group-egress \
  --group-id $SG_ID \
  --protocol -1 \
  --cidr 0.0.0.0/0

echo "VPC=$VPC_ID, Subnets=$SUBNETS, SG=$SG_ID"
```

---

## 9. Configurar GitHub Secrets

No seu repositório GitHub, adicione em **Settings → Secrets and variables → Actions**:

| Secret | Valor |
|--------|-------|
| `AWS_ACCOUNT_ID` | (resultado de `aws sts get-caller-identity`) |
| `AWS_REGION` | `us-east-1` ou sua região |
| `AWS_ROLE_TO_ASSUME` | `arn:aws:iam::ACCOUNT_ID:role/GitHubActionsRole-imdb-scraper` |
| `ECS_CLUSTER` | `imdb` |
| `ECS_TASK_DEFINITION` | `imdb-scraper` |
| `ECS_SUBNETS` | (de passo 8) ex: `subnet-123,subnet-456` |
| `ECS_SECURITY_GROUPS` | (de passo 8) ex: `sg-789` |
| `S3_BUCKET` | seu bucket (ex: `my-imdb-datalake`) |
| `S3_PREFIX` | `imdb/` |
| `SCRAPE_URL` | `https://www.imdb.com/pt/search/title/?title_type=video_game` |

---

## 10. Testar Localmente (Optional)

```bash
# Build da imagem
docker build -t imdb-scraper:latest .

# Correr localmente
docker run --rm \
  -e AWS_REGION=us-east-1 \
  -e S3_BUCKET=my-imdb-datalake \
  -e S3_PREFIX=imdb/ \
  -v ~/.aws:/root/.aws \
  imdb-scraper:latest
```

---

## 11. Testar GitHub Actions

1. Faça push das mudanças para o repositório
2. Vá para **Actions** na abeta do GitHub
3. Selecione workflow `Scrape IMDb to S3 via ECS`
4. Clique em **Run workflow** (botão verde)
5. Monitore o progresso e logs

---

## 12. Verificar S3 Upload

```bash
# Listar arquivos no bucket
aws s3 ls s3://$BUCKET_NAME/imdb/ --recursive

# Download de arquivo (para teste)
aws s3 cp s3://$BUCKET_NAME/imdb/imdb_filmes*.jsonl.gz . && gunzip -c imdb_filmes*.jsonl.gz | head -5
```

---

## 13. Próximo: Databricks Integration (Veja DATABRICKS_SETUP.md)

---

## Troubleshooting

### ECS Task falha com "No space left on device"
- Aumentar memory na task definition (512 → 1024)
- Ou reduzir número de páginas no scraper

### S3 upload falha ("Access Denied")
- Verificar role ARN na task definition
- Verificar policy no role (recurso correto?)
- Verificar bucket name

### GitHub Actions falha no login ECR
- Verificar OIDC provider e role trust policy
- Verificar `AWS_ROLE_TO_ASSUME` secret
- Ver logs do workflow

### Playwright crashes ("no Chromium found")
- Dockerfile já inclui Playwright + browsers
- Garantir que imagem base é `mcr.microsoft.com/playwright/python`

---

Para suporte: Consulte AWS docs ou logs CloudWatch via:
```bash
aws logs tail /ecs/imdb-scraper --follow
```
