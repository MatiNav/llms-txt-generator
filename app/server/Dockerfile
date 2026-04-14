FROM python:3.12-slim

WORKDIR /srv

COPY app/shared /srv/app/shared
COPY app/server /srv/app/server

RUN pip install --no-cache-dir -e /srv/app/shared -e /srv/app/server

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/srv/app/server"]
