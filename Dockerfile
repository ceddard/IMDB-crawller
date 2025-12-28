# Use official Playwright Python image with browsers preinstalled
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install --with-deps

COPY run.py /app/run.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/run.py"]