# ─── Worker 镜像 ──────────────────────────────────────────────────────────────
# 基于与 data_service 相同的基础环境，额外安装 Celery 依赖
FROM python:3.11-slim

# 系统依赖（GDAL / rasterio 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev gcc g++ libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        celery[rabbitmq]==5.3.6 \
        redis==5.0.3 \
        psycopg2-binary==2.9.9 \
        flower==2.0.1

# 复制项目代码
COPY . .

# 存储挂载点
VOLUME ["/storage"]

# 默认启动 4 并发 Worker，监听所有队列
CMD ["celery", "-A", "worker_cluster.app.celery_app", "worker", \
     "--loglevel=info", \
     "--concurrency=4", \
     "-Q", "preprocess,export,index,extraction"]