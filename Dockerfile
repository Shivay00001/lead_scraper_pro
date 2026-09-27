FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps for Playwright/Chromium headless scraping
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

# Drop privileges
RUN useradd -m -u 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

# Env-driven config: see .env.example
ENV LSP_DB_PATH=/app/data/leads.db

HEALTHCHECK --interval=60s --timeout=15s --start-period=30s --retries=3 \
    CMD python main.py health --json || exit 1

ENTRYPOINT ["python", "main.py"]
CMD ["health", "--json"]
