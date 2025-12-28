from playwright.sync_api import sync_playwright
import csv
import math
import os
import json
import gzip
from datetime import datetime, timezone
import pandas as pd
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env se existir
load_dotenv()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    # Adicionando um User-Agent para evitar bloqueios básicos
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    scrape_url = os.getenv("SCRAPE_URL", "https://www.imdb.com/pt/search/title/?title_type=video_game")
    print(f"Iniciando scraping de: {scrape_url}")
    page.goto(scrape_url)
    
    # Espera o carregamento inicial da lista
    try:
        page.wait_for_selector(".ipc-metadata-list-summary-item", timeout=15000)
    except Exception:
        print("Aviso: Seletor de itens não encontrado no tempo esperado. Verificando conteúdo...")

    per_page = 50
    total_text = None
    # Seletor atualizado para o total de resultados
    total_el = page.query_selector(".sc-2d056ab8-3.fhbjmI") or page.query_selector("[data-testid='dli-titles-metadata']")
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
        # Tenta seletores diferentes para os itens da lista
        items = page.query_selector_all(".ipc-metadata-list-summary-item") or \
                page.query_selector_all("[data-testid='dli-parent']")
        
        print(f"Encontrados {len(items)} itens nesta página.")
        
        if len(items) == 0:
            # Se não achou nada, tira um print para debug (opcional)
            # page.screenshot(path=f"debug_page_{page_index}.png")
            print("Nenhum item encontrado. Verifique se a página carregou corretamente.")

        for item in items:
            try:
                title_el = item.query_selector(".ipc-title__text") or \
                           item.query_selector("h3")
                title = title_el.inner_text() if title_el else None

                metadata = item.query_selector_all(".dli-title-metadata-item") or \
                           item.query_selector_all(".sc-b189961a-8")
                year = metadata[0].inner_text() if metadata else None

                rating_el = item.query_selector(".ipc-rating-star--base") or \
                            item.query_selector("[aria-label^='IMDb rating']")
                rating = rating_el.inner_text().split()[0] if rating_el else None
                
                if title:
                    data.append({
                        "title": title,
                        "year": year,
                        "rating": rating,
                        "page": page_index,
                        "source_url": scrape_url,
                        "scraped_at_utc": datetime.now(timezone.utc).isoformat()
                    })
            except Exception:
                pass

        # O IMDb novo usa um botão "Load More" (Ver mais) em vez de paginação tradicional
        next_button = page.query_selector("button.ipc-see-more__button") or \
                      page.query_selector(".ipc-see-more__button") or \
                      page.query_selector("a[rel='next']")
        
        if next_button:
            try:
                print("Botão 'Ver mais' encontrado. Carregando próxima leva...")
                next_button.scroll_into_view_if_needed()
                next_button.click()
                # Espera os novos itens carregarem
                page.wait_for_timeout(3000) 
                page_index += 1
                
                # Limite de segurança para não rodar infinitamente em testes
                if page_index > 200: 
                    break
            except Exception as e:
                print(f"Erro ao clicar no botão: {e}")
                break
        else:
            print("Fim da lista ou botão 'Ver mais' não encontrado.")
            break

    try:
        # Corrigindo o formato do timestamp para Windows (sem colons)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
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