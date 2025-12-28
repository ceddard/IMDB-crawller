from playwright.sync_api import sync_playwright
import csv
import math
import os
import json
import gzip
from datetime import datetime
import pandas as pd
import boto3
from botocore.exceptions import BotoCoreError, ClientError


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    scrape_url = os.getenv("SCRAPE_URL", "https://www.imdb.com/pt/search/title/?title_type=video_game")
    page.goto(scrape_url)
    
    per_page = 50
    total_text = None
    total_el = page.query_selector(".sc-2d056ab8-3.fhbjmI")
    if total_el:
        try:
            total_text = total_el.inner_text()
            import re
            m = re.search(r'([0-9][0-9\.,]*)$', total_text.strip())
            if m:
                digits = ''.join(ch for ch in m.group(1) if ch.isdigit())
                total = int(digits) if digits else 0
                pages = math.ceil(total / per_page)
                print(f"Total resultados: {total} -> iterações necessárias (por {per_page}): {pages}")
            else:
                total_text = None
        except:
            total_text = None

    data = []
    page_index = 1
    while True:
        print(f"Visitando página {page_index}")
        items = page.query_selector_all(".ipc-metadata-list-summary-item")
        print(f"Encontrados {len(items)} itens nesta página.")
        for item in items:
            try:
                title_el = item.query_selector(".ipc-title__text")
                title = title_el.inner_text() if title_el else None

                metadata = item.query_selector_all(".dli-title-metadata-item")
                year = metadata[0].inner_text() if metadata else None

                rating_el = item.query_selector(".ipc-rating-star--base")
                rating = rating_el.inner_text().split()[0] if rating_el else None
                data.append({
                    "title": title,
                    "year": year,
                    "rating": rating,
                    "page": page_index,
                    "source_url": scrape_url,
                    "scraped_at_utc": datetime.utcnow().isoformat()
                })
            except Exception:
                pass

        next_link = page.query_selector('a[rel="next"]')
        if not next_link:
            next_link = page.query_selector("a:has-text('Next')") or page.query_selector("a:has-text('Próximo')") or page.query_selector("a:has-text('Próxima')")
        if next_link:
            try:
                next_link.click()
                page.wait_for_load_state('networkidle')
                page.wait_for_timeout(1000)
                page_index += 1
            except Exception:
                print("Erro ao clicar em next; parando iterações.")
                break
        else:
            print("Link 'next' não encontrado; finalizando varredura.")
            break

    # Persistir como JSONL GZIP e enviar ao S3 (opcional)
    try:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        out_jsonl = os.getenv("OUT_JSONL", f"imdb_filmes_{timestamp}.jsonl.gz")
        with gzip.open(out_jsonl, "wt", encoding="utf-8") as f:
            for row in data:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"JSONL GZIP salvo: {out_jsonl}")

        s3_bucket = os.getenv("S3_BUCKET", "datalake-imdb-656661782834-staging")
        s3_prefix = os.getenv("S3_PREFIX", "imdb/")
        if s3_bucket:
            s3_key = s3_prefix.rstrip("/") + "/" + os.path.basename(out_jsonl)
            try:
                s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
                s3.upload_file(out_jsonl, s3_bucket, s3_key)
                print(f"Enviado ao S3: s3://{s3_bucket}/{s3_key}")
            except (BotoCoreError, ClientError) as e:
                print("Falha no upload S3:", e)
    except Exception as e:
        print("Erro ao salvar/enviar JSONL:", e)