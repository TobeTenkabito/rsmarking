#!/bin/bash

echo "Building Docker image..."

cd executor_service/runtime

# Build the worker runtime image.
docker build -t rs-worker-python:latest -f python_base.Dockerfile .

if [ $? -eq 0 ]; then
    echo "Image built successfully!"
    docker images | grep rs-worker-python
else
    echo "Image build failed!"
    exit 1
fi
