#!/bin/bash

echo "构建Docker镜像..."

cd executor_service/runtime

# 构建镜像
docker build -t rs-worker-python:latest -f python_base.Dockerfile .

if [ $? -eq 0 ]; then
    echo "镜像构建成功！"
    docker images | grep rs-worker-python
else
    echo "镜像构建失败！"
    exit 1
fi
