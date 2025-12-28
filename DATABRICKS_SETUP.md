# Integração Databricks com Auto Loader

## 1. Pré-requisitos Databricks

- [ ] Unity Catalog habilitado no workspace
- [ ] SQL warehouse provisionado
- [ ] Permissões CREATE TABLE no catálogo/esquema

---

## 2. Criar External Location (Unity Catalog)

### 2.1 Via Databricks UI

1. **Admin Console** → **Data** → **External Locations**
2. Clique em **Create external location**
3. **Name**: `imdb_s3_landing`
4. **URL**: `s3://YOUR_BUCKET/imdb/`
5. **Storage credential**: (selecionar ou criar)
   - Se criar, configure AWS cross-account IAM role ou Access Key
   - Role ARN: `arn:aws:iam::YOUR_AWS_ACCOUNT:role/DatabricksS3Role` (exemplo)

6. Clique em **Create**

### 2.2 Via SQL (alternativo)

```sql
CREATE EXTERNAL LOCATION imdb_s3_landing
  URL 's3://your-bucket/imdb/'
  WITH (STORAGE_CREDENTIAL = 'aws-credential-name');
```

---

## 3. Criar Schema no Catálogo

```sql
-- Conecte-se ao warehouse e execute:
CREATE SCHEMA IF NOT EXISTS main.imdb_data;

-- Mudar para o schema
USE SCHEMA main.imdb_data;

-- Criar pasta para checkpoints (Auto Loader)
CREATE EXTERNAL VOLUME imdb_volume
  LOCATION 's3://your-bucket/imdb-checkpoints/';
```

---

## 4. Criar Auto Loader Job (Streaming)

### Opção A: Notebook com Auto Loader

Crie um notebook (`Databricks/autoloader_imdb.py` ou `.sql`) com:

```python
# Python
from pyspark.sql.types import *

s3_path = "s3://your-bucket/imdb/"
checkpoint_path = "s3://your-bucket/imdb-checkpoints/"

df = (spark.readStream
      .format("cloudFiles")
      .option("cloudFiles.format", "json")
      .option("cloudFiles.inferColumnTypes", "true")
      .option("cloudFiles.schemaEvolutionMode", "rescued")
      .option("cloudFiles.schemaHints", """
        title STRING,
        year STRING,
        rating STRING,
        page LONG,
        source_url STRING,
        scraped_at_utc STRING
      """)
      .option("cloudFiles.includeExistingFiles", "true")
      .load(s3_path))

# Escrever na tabela Delta
(df.writeStream
   .format("delta")
   .option("checkpointLocation", checkpoint_path)
   .option("mergeSchema", "true")
   .mode("append")
   .toTable("main.imdb_data.imdb_titles"))
```

Ou SQL:

```sql
CREATE OR REPLACE TABLE main.imdb_data.imdb_titles (
  title STRING,
  year STRING,
  rating STRING,
  page LONG,
  source_url STRING,
  scraped_at_utc STRING,
  _rescue_data STRING
);

CREATE OR REPLACE STREAMING LIVE TABLE imdb_titles_live
COMMENT "IMDb data via Auto Loader"
AS
SELECT * FROM cloud_files(
  location => 's3://your-bucket/imdb/',
  format => 'json',
  schemaEvolutionMode => 'rescued'
);
```

### Opção B: Databricks Job (agendado)

1. **Workflows** → **Jobs** → **Create job**
2. **Task**: selecionar notebook criado acima
3. **Cluster**: usar existing cluster ou job cluster
4. **Schedule**: (opcional) executar diariamente após GitHub Actions disparar
5. Salvar e **Run Now** para testar

---

## 5. Monitorar Ingestão

### Via SQL

```sql
-- Contar registros
SELECT COUNT(*) as total_records FROM main.imdb_data.imdb_titles;

-- Ver registros mais recentes
SELECT * FROM main.imdb_data.imdb_titles
  ORDER BY scraped_at_utc DESC
  LIMIT 10;

-- Verificar dados resgatados (schema evolution)
SELECT * FROM main.imdb_data.imdb_titles
  WHERE _rescue_data IS NOT NULL
  LIMIT 10;

-- Histórico de versões
DESCRIBE HISTORY main.imdb_data.imdb_titles;
```

### Via Python (em Databricks)

```python
df = spark.table("main.imdb_data.imdb_titles")
df.printSchema()
df.show(5)
df.groupBy("year").count().show()
```

---

## 6. Schema Evolution & Rescued Data

**O que acontece quando os dados mudarem?**

### Exemplo 1: Coluna Nova
```json
// Nova entrada com campo extra
{"title": "Game X", "year": "2025", "rating": "8.5", "director": "John Doe"}
```

✅ **Auto Loader reage**:
- Detecta `director` (coluna nova)
- Adiciona coluna automaticamente à tabela
- Colunas antigas mantêm NULL

### Exemplo 2: Tipo de Dado Errado
```json
{"title": "Game Y", "year": "twenty-twenty", "rating": "not-a-number"}
```

✅ **Auto Loader resgata**:
- Coloca a linha malformada em `_rescue_data` (STRING)
- Resto dos dados (title) vai normal
- Você pode corrigir depois com SQL:
  ```sql
  SELECT *, from_json(_rescue_data, schema_of_json(...)) as rescued
  FROM main.imdb_data.imdb_titles
  WHERE _rescue_data IS NOT NULL;
  ```

---

## 7. Particionamento (Opcional)

Se quiser particionar por data:

```sql
-- Adicionar coluna de partição
ALTER TABLE main.imdb_data.imdb_titles
  ADD COLUMN scrape_date DATE
  DEFAULT CAST(CAST(substr(scraped_at_utc, 1, 10) AS STRING) AS DATE);

-- Particionar futuros arquivos (opcional, mas melhora performance)
-- Reescrever com partição:
OPTIMIZE main.imdb_data.imdb_titles ZORDER BY (scrape_date);
```

---

## 8. Criar Dashboards / BI

### Exemplo: Notebook de Análise

```sql
%sql
SELECT 
  year,
  COUNT(*) as count,
  AVG(CAST(rating AS FLOAT)) as avg_rating
FROM main.imdb_data.imdb_titles
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year DESC;
```

Visualizar como gráfico (Databricks UI: **+** → **Visualization**).

---

## 9. Troubleshooting

### Auto Loader não está processando novos arquivos
- Verificar se external location está com permissões corretas
- Verificar se `cloudFiles.includeExistingFiles=true` está setado
- Checar logs do job:
  ```sql
  DESCRIBE HISTORY main.imdb_data.imdb_titles;
  ```

### Erro "Location not found" ou "Access Denied"
- Testar access ao S3:
  ```python
  spark.read.json("s3://your-bucket/imdb/*.jsonl.gz").show()
  ```
- Verificar credenciais AWS (storage credential)
- Verificar policy do IAM role (S3:GetObject, S3:ListBucket)

### Schema conflicts
- Auto Loader com `schemaEvolutionMode=rescued` + `mergeSchema=true` deve lidar
- Se falhar, ver coluna `_rescue_data` para os erros

---

## 10. Performance Tips

1. **Compressão GZIP**: Script já faz isso (imdb_filmes.jsonl.gz)
   - Reduz espaço S3, Auto Loader descomprime automático

2. **Partitionamento S3 por data**:
   ```
   s3://bucket/imdb/
     ├── 2025-01-01/imdb_filmes_2025-01-01T03:00:00.jsonl.gz
     ├── 2025-01-02/imdb_filmes_2025-01-02T03:00:00.jsonl.gz
   ```
   Script pode ser adaptado para isso

3. **Índices Delta**: 
   ```sql
   CREATE LIQUID CLUSTERING ON main.imdb_data.imdb_titles (year, title);
   ```

4. **Retenção**: limpar checkpoints antigos
   ```bash
   aws s3 rm s3://bucket/imdb-checkpoints/ --recursive --exclude "*" --include "*" --region us-east-1 --dryrun
   ```

---

## 11. Próximas Etapas

- [ ] Testar job Auto Loader com arquivo manual no S3
- [ ] Validar ingestão (contar registros, verificar schema)
- [ ] Automatizar trigger (GitHub Actions → Databricks job via webhook/API)
- [ ] Criar alertas (CloudWatch / Databricks alerts)
- [ ] Documentar SLA (frequência de ingestão, latência esperada)

---

## Referências

- [Databricks Auto Loader](https://docs.databricks.com/en/ingestion/auto-loader/index.html)
- [Schema Evolution](https://docs.databricks.com/en/ingestion/auto-loader/schema.html)
- [Unity Catalog External Locations](https://docs.databricks.com/en/connect/unity-catalog/external-locations.html)
