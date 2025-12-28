# IMDb Scraper: Arquitetura Completa AWS + Databricks

## 1. Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                      GitHub Actions (CI/CD)                         │
│  - Trigger via webhook, schedule ou manual                          │
│  - Build Docker image, Push to ECR                                  │
│  - Dispara ECS Fargate task com env vars                            │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│              AWS ECR (Elastic Container Registry)                   │
│  - Armazena imagem Docker do scraper                                │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│           AWS ECS Fargate (Serverless Container)                    │
│  - Executa container (Python + Playwright + boto3)                  │
│  - headless=true (sem interface gráfica)                            │
│  - Injeta env vars: AWS_REGION, S3_BUCKET, SCRAPE_URL, etc.       │
│  - IAM Task Role: S3:PutObject                                      │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│         AWS S3 (Landing Zone / Data Lake)                           │
│  - Bucket: imdb-scraped-data (ou seu nome)                          │
│  - Prefix: imdb/                                                    │
│  - Arquivo: imdb_filmes.jsonl.gz (NDJSON comprimido)                │
│  - External Location (UC): mapeado para este path                   │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼ (notificação ou polling)
┌─────────────────────────────────────────────────────────────────────┐
│    Databricks Auto Loader (cloudFiles, schema evolution)            │
│  - Lê JSONL.GZ do S3 (novo arquivo dispara ingestão)                │
│  - Auto Loader = sem schema pré-definido, sem travamento            │
│  - Schema Evolution: adiciona colunas novas automaticamente          │
│  - Rescued Data: dados com tipo errado vão para _rescue_data        │
│  - Merge Schema: garante consistência na tabela Delta               │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│   Databricks Delta Lake (catálogo.esquema.imdb_titles)              │
│  - Tabela Unity Catalog                                             │
│  - Colunas: title, year, rating, page, source_url, scraped_at_utc   │
│  - _rescue_data: coluna automática com dados malformados            │
│  - Versionamento automático                                         │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. Componentes e Responsabilidades

### 2.1 Python Script (`IMDB-crawller/run.py`)
- **O quê**: Extrai títulos, anos e notas do IMDb
- **Como**: Playwright (headless=True no ECS)
- **Saída**: JSONL + gzip → S3
- **Env Vars**:
  - `SCRAPE_URL`: URL do IMDb (padrão: video_game)
  - `OUT_JSONL`: nome do arquivo local (padrão: imdb_filmes.jsonl.gz)
  - `AWS_REGION`: region AWS (ex: us-east-1)
  - `S3_BUCKET`: seu bucket S3
  - `S3_PREFIX`: prefixo (ex: imdb/)

### 2.2 Docker
- **Imagem Base**: `mcr.microsoft.com/playwright/python:v1.49.0-focal`
- **Deps**: Playwright, Pandas, PyArrow, boto3
- **Entrypoint**: `python /app/run.py`
- **Build & Push**: GitHub Actions → ECR

### 2.3 GitHub Actions Workflow (`.github/workflows/scrape.yml`)
1. **Trigger**: manual, schedule ou webhook
2. **OIDC**: assume AWS role (sem keys hardcoded)
3. **Build**: docker build + tag
4. **Push**: ECR
5. **Run**: dispara ECS task com env overrides

### 2.4 AWS ECS (Fargate)
- **Cluster**: seu cluster ECS existente
- **Task Definition**: imdb-scraper
  - Container: `app` (imagem ECR)
  - CPU: 256 (0.25), Memory: 512 MB (mínimo Fargate)
  - IAM Task Role: s3:PutObject, CloudWatch Logs
- **Service/Task**: run-task sem serviço de longa vida (dispara sob demanda)

### 2.5 AWS S3
- **Bucket**: seu bucket (ex: company-datalake-prod)
- **Estrutura**:
  ```
  s3://bucket/imdb/
                  ├── imdb_filmes_2025-01-01T03:00:00.jsonl.gz
                  ├── imdb_filmes_2025-01-02T03:00:00.jsonl.gz
                  └── ...
  ```
- **Lifecycle**: (opcional) arquivar após 90 dias, deletar após 1 ano

### 2.6 Databricks Auto Loader
- **Leitura**: S3 path como external location (UC)
- **Format**: JSON (cada linha é um JSON)
- **Schema Evolution**: true → colunas novas não travam
- **Rescued Data**: true → tipos errados em `_rescue_data`
- **Escrita**: Delta table com `mergeSchema=true`

## 3. Fluxo de Execução (fim-a-fim)

1. **GitHub Actions trigger** (manual ou 3 AM UTC diariamente)
   ```
   Run workflow → build image → push ECR
   ```

2. **Dispara ECS task**
   ```
   aws ecs run-task --cluster imdb --task-definition imdb-scraper \
     --overrides '{...env vars...}'
   ```

3. **Container inicia no Fargate**
   ```
   python /app/run.py
   ├── Cria browser headless
   ├── Navega IMDb e coleta dados
   ├── Escreve JSONL.GZ localmente
   ├── Upload via boto3 → S3
   └── Exit 0
   ```

4. **S3 recebe arquivo**
   ```
   s3://bucket/imdb/imdb_filmes.jsonl.gz
   ├── Databricks Auto Loader detecta novo arquivo
   └── Inicia ingestão streaming
   ```

5. **Databricks processa**
   ```
   Auto Loader lê JSONL
   ├── Schema evolution (colunas novas)
   ├── Rescued data (tipos errados)
   └── Merge na tabela Delta imdb_titles
   ```

6. **Resultado final**
   ```
   Tabela Unity Catalog:
   - catalog.schema.imdb_titles (particionada por scrape_date ou não)
   - Dados prontos para análise/BI
   ```

## 4. Pré-requisitos AWS

- [ ] Conta AWS com permissões
- [ ] ECR repository (vazio ou existente)
- [ ] ECS cluster (Fargate)
- [ ] S3 bucket para landing zone
- [ ] IAM role para ECS task (S3:PutObject, CloudWatch)
- [ ] IAM role para GitHub OIDC (assume role)
- [ ] VPC/Subnets/Security group (para Fargate)

## 5. Pré-requisitos Databricks

- [ ] Workspace com SQL warehouse
- [ ] Unity Catalog habilitado
- [ ] External location mapeado ao S3 bucket
- [ ] Permissões CREATE TABLE no schema

## 6. Benefícios desta Arquitetura

| Aspecto | Benefício |
|---------|-----------|
| **Custo** | Fargate (pay-per-execution), S3 (storage barato), Databricks (Auto Loader sem overhead) |
| **Robustez** | Container isolado, sem dependências locais, retry automático |
| **Escalabilidade** | Fargate escala automaticamente, S3 é ilimitado, Auto Loader aguarda sem travamento |
| **Schema Evolution** | Auto Loader não requer schema pré-definido, rescata dados sujos |
| **CI/CD** | GitHub Actions automatiza build, push, deploy |
| **Segurança** | OIDC (sem keys), IAM roles, S3 privado, VPC isolado |

## 7. Próximos Passos

1. **Setup AWS**
   - Criar IAM roles (GitHub OIDC, ECS task)
   - Criar S3 bucket
   - Criar/atualizar ECS cluster e task definition
   - Configurar GitHub secrets

2. **Setup Databricks**
   - Criar external location (Unity Catalog)
   - Criar notebook com Auto Loader
   - Testar ingestão com arquivo de teste

3. **Validação**
   - Rodar script localmente (com env vars)
   - Build e push Docker image
   - Disparar GitHub Actions
   - Monitorar CloudWatch logs
   - Validar S3 upload
   - Validar ingestão Databricks

---

## Referências

- [AWS ECS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/launch_types.html)
- [Databricks Auto Loader](https://docs.databricks.com/en/ingestion/auto-loader/index.html)
- [GitHub OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [Unity Catalog External Locations](https://docs.databricks.com/en/connect/unity-catalog/external-locations.html)
