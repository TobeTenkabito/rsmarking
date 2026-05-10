# worker_cluster

`worker_cluster` is the Celery-based offline execution layer for long-running raster and vector jobs.

## Current status

The folder contains real task implementations and, after the registration fix in `app.py`, a worker can load and execute them. The main FastAPI routes in `services/data_service` are still mostly synchronous, so this cluster is not yet the default execution path for the product.

What works now:
- Celery workers can import and execute the task modules under `worker_cluster/tasks`.
- Progress is written to Redis through `BaseRasterTask.report(...)`.
- Optional `task_jobs` persistence is available when you submit work through `worker_cluster/producer.py`.

What is still not fully wired:
- `services/data_service/routers/*.py` still call raster processing functions inline instead of enqueueing Celery tasks.
- The worker Docker image still needs its dependency path refreshed before it becomes the easiest startup method. The documented path below uses the repo's Python environment plus Dockerized infra.

## Available tasks

Preprocess:
- `worker_cluster.tasks.preprocess.build_cog`
- `worker_cluster.tasks.preprocess.build_overviews`
- `worker_cluster.tasks.preprocess.reproject`
- `worker_cluster.tasks.preprocess.compute_statistics`

Index:
- `worker_cluster.tasks.index.ndvi`
- `worker_cluster.tasks.index.ndwi`
- `worker_cluster.tasks.index.ndbi`
- `worker_cluster.tasks.index.mndwi`
- `worker_cluster.tasks.index.calculator`

Export:
- `worker_cluster.tasks.export.geojson`

## Prerequisites

1. Create the Python environment from the repo `environment.yml`, or otherwise install the packages listed there, including `celery`, `redis`, `sqlalchemy`, `psycopg2-binary`, `rasterio`, and project dependencies.
2. Start infrastructure from `infrastructure/docker/docker-compose.yml`:

```powershell
cd infrastructure/docker
docker-compose up -d
```

This now starts:
- PostgreSQL/PostGIS on `localhost:5432`
- RabbitMQ on `localhost:5672`
- RabbitMQ management UI on `http://localhost:15672`
- Redis on `localhost:6379`

3. Run database migrations, including the new `task_jobs` table migration:

```powershell
cd infrastructure/db_migrations
alembic upgrade head
cd ..\annot_migrations
alembic upgrade head
```

## Important environment variables

Defaults already match the local docker-compose values:

```text
DATABASE_URL=postgresql+asyncpg://rs_admin:rs_password@localhost:5432/rsmarking
SYNC_DATABASE_URL=postgresql+psycopg2://rs_admin:rs_password@localhost:5432/rsmarking
CELERY_BROKER_URL=amqp://rs_admin:rs_password@localhost:5672/rsmarking_vhost
CELERY_RESULT_BACKEND=redis://localhost:6379/0
WORKER_CONCURRENCY=4
EXPORT_DIR=/storage/exports
```

## Start a worker

From the repo root:

```powershell
celery -A worker_cluster.app.celery_app worker --loglevel=info --concurrency=4 -Q preprocess,index,export
```

If you want to inspect queues and task events, you can also run Flower:

```powershell
celery -A worker_cluster.app.celery_app flower --port=5555
```

## Submit tasks

### Option 1: submit by task name with the helper

```python
from worker_cluster.producer import submit_task

job = submit_task(
    "worker_cluster.tasks.preprocess.build_cog",
    task_type="convert_cog",
    kwargs={
        "index_id": 202605100001,
        "raw_path": r"F:\rsmarking\storage\raw\scene.tif",
        "cog_path": r"F:\rsmarking\storage\cog\scene_cog.tif",
    },
    raster_index_id=202605100001,
)

print(job)
```

Example response:

```python
{
    "job_id": "9fd6...",
    "task_id": "f1c2...",
    "queue": "preprocess",
    "job_recorded": True,
}
```

If `job_recorded` is `False`, the task was still submitted, but the `task_jobs`
table was not available. In that case, use the returned `task_id` plus Redis
status tracking.

### Option 2: call the task object directly

```python
from worker_cluster.tasks.index.spectral import ndvi_task

result = ndvi_task.delay(
    red_path=r"F:\rsmarking\storage\raw\red.tif",
    nir_path=r"F:\rsmarking\storage\raw\nir.tif",
    output_path=r"F:\rsmarking\storage\raw\ndvi_raw.tif",
)

print(result.id)
```

This is fine for quick testing, but it does not create a `task_jobs` record by itself.

## Check status

### Fast progress from Redis

```python
from worker_cluster.bridge.status_reporter import get_task_status

status = get_task_status("<celery-task-id>")
print(status)
```

Typical payload:

```python
{
    "task_id": "...",
    "status": "running",
    "progress": 70,
    "message": "Building overviews",
    "result": {},
    "updated_at": "2026-05-10T00:00:00+00:00",
}
```

### Celery result backend

```python
from celery.result import AsyncResult
from worker_cluster.app import celery_app

result = AsyncResult("<celery-task-id>", app=celery_app)
print(result.state, result.info)
```

## How task status works

- `BaseRasterTask.before_start` writes `running` to Redis immediately.
- Tasks can call `self.report(progress, message)` during execution.
- `BaseRasterTask.on_success`, `on_failure`, and `on_retry` write final or retry state back to Redis.
- If the task was submitted through `submit_task(...)`, the worker also updates the `task_jobs` row by using the `job_id` passed in Celery headers.

## Recommended integration path

If you want to adopt `worker_cluster` in `data_service`, the clean next step is:

1. Replace synchronous calls in `services/data_service/db_ops.py` with `submit_task(...)`.
2. Return `job_id` and `task_id` from the API immediately.
3. Add a status route that reads Redis via `get_task_status(...)`.
4. Keep the existing synchronous code path only for tests or very small jobs.
