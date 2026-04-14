FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app

COPY app/shared ./app/shared
RUN pip install --no-cache-dir -e ./app/shared

COPY app/handlers/ecs_tasks/spa_fetcher/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/handlers ./handlers
CMD ["python", "-m", "handlers.ecs_tasks.spa_fetcher.main"]
