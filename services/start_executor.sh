#!/bin/bash

# 构建Docker镜像（如果不存在）
if ! docker images | grep -q "rs-worker-python"; then
    echo "Docker镜像不存在，开始构建..."
    bash build_docker.sh
fi

# 启动执行服务
echo "启动执行服务 (端口 8004)..."
cd executor_service
python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload
