FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY app/shared ./app/shared
RUN pip install --no-cache-dir -e ./app/shared

COPY app/handlers/ecs_tasks/spa_fetcher/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY app/handlers ./app/handlers
CMD ["python", "-m", "handlers.ecs_tasks.spa_fetcher.main"]
