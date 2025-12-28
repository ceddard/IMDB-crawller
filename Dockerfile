# Python base image - slim for smaller size
FROM python:3.13-slim

# Metadata
LABEL maintainer="IMDb Crawler"
LABEL version="1.0"
LABEL description="IMDb GraphQL Crawler with HTTP/2 and adaptive backoff"

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 crawler && \
    mkdir -p /app/output /app/state && \
    chown -R crawler:crawler /app

# Install dependencies first (better layer caching)
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=crawler:crawler run.py /app/
COPY --chown=crawler:crawler service/ /app/service/

# Switch to non-root user
USER crawler

# Environment variables with sensible defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PER_PAGE=1000 \
    MAX_PAGES=all \
    WORKER_COUNT=24 \
    RESUME=true \
    HTTP_POOL_CONNECTIONS=40 \
    HTTP_POOL_MAXSIZE=100 \
    HTTP_TIMEOUT=30

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python run.py" || exit 1

# Run the crawler
CMD ["python", "run.py"]