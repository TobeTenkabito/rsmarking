#!/bin/bash

# Build the Docker image if it is missing.
if ! docker images | grep -q "rs-worker-python"; then
    echo "Docker image is missing; starting build..."
    bash build_docker.sh
fi

# Start the executor service.
echo "Starting executor service on port 8004..."
cd executor_service
python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload
