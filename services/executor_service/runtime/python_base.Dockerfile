# 采用 slim 版本减小攻击面和拉取体积
FROM python:3.10-slim

# 设置环境变量，禁止生成 .pyc 文件，强制无缓冲输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装系统级依赖 (GDAL 依赖)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装遥感核心库
RUN pip install --no-cache-dir \
    numpy \
    scipy \
    rasterio \
    opencv-python-headless \
    numexpr

# 创建工作目录和非 root 用户（安全要求）
RUN useradd -m -s /bin/bash sandboxuser
WORKDIR /app

# 复制引导脚本并赋予执行权限
COPY sandbox_entry.py /app/sandbox_entry.py
RUN chown sandboxuser:sandboxuser /app/sandbox_entry.py && chmod +x /app/sandbox_entry.py

# 切换到非 root 用户
USER sandboxuser

# 默认入口
ENTRYPOINT ["python", "/app/sandbox_entry.py"]