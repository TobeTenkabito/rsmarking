# ─── Worker text ──────────────────────────────────────────────────────────────
# text data_service text,text Celery text
FROM python:3.11-slim

# text(GDAL / rasterio text)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev gcc g++ libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# text,text Docker text
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        celery[rabbitmq]==5.3.6 \
        redis==5.0.3 \
        psycopg2-binary==2.9.9 \
        flower==2.0.1

# text
COPY . .

# text
VOLUME ["/storage"]

# text 4 text Worker,text
CMD ["celery", "-A", "worker_cluster.app.celery_app", "worker", \
     "--loglevel=info", \
     "--concurrency=4", \
     "-Q", "preprocess,export,index,extraction"]