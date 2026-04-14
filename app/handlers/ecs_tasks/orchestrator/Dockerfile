FROM python:3.12-slim

WORKDIR /app

COPY app/shared ./app/shared
RUN pip install --no-cache-dir -e ./app/shared

COPY app/handlers/ecs_tasks/orchestrator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/handlers/ecs_tasks/orchestrator ./orchestrator
CMD ["python", "-m", "orchestrator.main"]
