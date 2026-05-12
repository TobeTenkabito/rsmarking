# RSMarking

RSMarking is a remote-sensing annotation and raster analysis workspace. It combines a browser map UI, FastAPI microservices, PostGIS-backed vector storage, GDAL/rasterio processing utilities, an AI gateway, and an optional Celery worker layer for longer-running jobs.

The repository is currently most useful as a local development stack for GeoTIFF upload, raster metadata management, on-the-fly map tiles, vector annotation, raster/vector analysis tools, AI-assisted analysis or metadata edits, and Docker-isolated custom Python scripts.

## Features

- Browser map client with Leaflet and Cesium-based 2D/3D viewing.
- GeoTIFF metadata ingestion with raw and COG storage directories.
- On-the-fly raster tile rendering from stored raster records.
- Vector projects, layers, features, attribute fields, shapefile import, and PostGIS spatial indexes.
- Vector tile service using PostGIS `ST_AsMVT`.
- Raster algorithms for NDVI, NDWI, NDBI, MNDWI, band extraction, band merge, raster calculator expressions, rasterization, clipping, and change detection.
- Extraction algorithms for vegetation, water, buildings, and clouds.
- AI gateway built around LiteLLM with analyze/modify modes and a callable function registry for analysis tools.
- Docker-isolated Python script executor with shared access to `storage/raw`.
- Optional Celery worker cluster for offline preprocessing, index calculation, and GeoJSON export jobs.

## Architecture

```text
client/index.html
  |
  | HTTP
  v
+----------------------+      +-----------------------+
| annotation_service   |      | data_service          |
| :8001                |      | :8002                 |
| projects/layers/     |      | uploads/metadata/     |
| features/fields      |      | raster algorithms     |
+----------+-----------+      +-----------+-----------+
           |                              |
           |                              |
           v                              v
+----------------------+      +-----------------------+
| vtile_service        |      | tile_service          |
| :8003                |      | :8005                 |
| PostGIS MVT tiles    |      | raster XYZ PNG tiles  |
+----------------------+      +-----------------------+

+----------------------+      +-----------------------+
| executor_service     |      | ai_gateway            |
| :8004                |      | :8006                 |
| Docker sandbox       |      | LiteLLM + validators  |
+----------------------+      +-----------------------+

PostgreSQL/PostGIS, Redis, and RabbitMQ are provided by infrastructure/docker/docker-compose.yml.
worker_cluster is optional and consumes RabbitMQ tasks while reporting status through Redis.
```

## Repository Map

```text
client/                         Static browser client
  index.html                    Main app shell
  packages/app/src/             App modules, API adapters, state, i18n
  packages/core/src/map.js      Leaflet/Cesium map engine
  packages/ui/src/              Modal and sidebar templates/components

services/
  annotation_service/           Vector projects, layers, features, fields
  data_service/                 Raster metadata, uploads, algorithms, bridges
  tile_service/                 Raster tile engine and Cython extensions
  vtile_service/                PostGIS vector tile endpoint
  executor_service/             Docker sandbox for custom Python scripts
  ai_gateway/                   AI analyze/modify gateway and tool registry

functions/
  implement/                    Core raster, vector, index, extraction algorithms
  common/                       Shared helpers such as Snowflake-style IDs

worker_cluster/                 Optional Celery worker layer
infrastructure/docker/          PostgreSQL/PostGIS, RabbitMQ, Redis compose file
infrastructure/*_migrations/    Alembic migrations for raster and vector DBs
storage/raw/                    Uploaded/original rasters and script outputs
storage/cog/                    Cloud-optimized GeoTIFF outputs
tests/                          Pytest, Vitest, and benchmark tests
resources/                      README screenshots and benchmark images
```

## Services

| Service | Port | Entry point | Main responsibility |
|---|---:|---|---|
| Annotation service | 8001 | `services.annotation_service.main:app` | Projects, layers, vector features, fields, shapefile import |
| Data service | 8002 | `services.data_service.main:app` | Raster metadata, uploads, spectral indices, extraction, clipping, scripts |
| Vector tile service | 8003 | `services.vtile_service.main:app` | MVT tiles from PostGIS |
| Executor service | 8004 | `services.executor_service.main:app` | Docker-isolated Python script execution |
| Tile service | 8005 | `services.tile_service.main:app` | Raster XYZ PNG tiles |
| AI gateway | 8006 | `services.ai_gateway.main:app` | AI analyze/modify requests and callable algorithm tools |

## Prerequisites

- Docker Desktop or Docker Engine with Compose.
- Conda or Mamba.
- Python 3.12. The checked-in `environment.yml` creates a Python 3.12 environment named `rsmarking`.
- A browser. The frontend is currently a static app; the committed `client/package.json` files are empty, so there is no working `npm run dev` script in this revision.
- Optional: Node.js if you want to add/restore frontend package scripts and run Vitest.

## Quick Start

From the repository root:

```powershell
conda env create -f environment.yml
conda activate rsmarking
```

Start infrastructure:

```powershell
cd infrastructure/docker
docker compose up -d
cd ../..
```

The compose file creates the `rsmarking` database. The annotation and vector tile services default to a separate `vector_db` database, so create it once:

```powershell
docker exec rsmarking-postgres createdb -U rs_admin vector_db
docker exec rsmarking-postgres psql -U rs_admin -d rsmarking -c "CREATE EXTENSION IF NOT EXISTS postgis;"
docker exec rsmarking-postgres psql -U rs_admin -d vector_db -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

If `vector_db` already exists, the first command can fail harmlessly.

Run database migrations:

```powershell
cd infrastructure/db_migrations
alembic upgrade head
cd ../annot_migrations
alembic upgrade head
cd ../..
```

Build the executor sandbox image if you plan to use custom scripts:

```powershell
docker build -t rs-worker-python:latest -f services/executor_service/runtime/python_base.Dockerfile services/executor_service/runtime
```

Start services in separate terminals from the repository root:

```powershell
python -m uvicorn services.annotation_service.main:app --host 0.0.0.0 --port 8001 --reload
python -m uvicorn services.data_service.main:app --host 0.0.0.0 --port 8002 --reload
python -m uvicorn services.vtile_service.main:app --host 0.0.0.0 --port 8003 --reload
python -m uvicorn services.executor_service.main:app --host 0.0.0.0 --port 8004 --reload
python -m uvicorn services.tile_service.main:app --host 0.0.0.0 --port 8005 --reload
python -m uvicorn services.ai_gateway.main:app --host 0.0.0.0 --port 8006 --reload
```

Open the client through the data service static mount:

```text
http://localhost:8002/client/index.html
```

You can also serve the repository root with any static file server and open `/client/index.html`.

## AI Gateway Configuration

The AI gateway loads `.env` from the repository root and calls LiteLLM. A minimal DeepSeek-style configuration looks like this:

```env
AI_MODEL=deepseek/deepseek-chat
AI_NAME=deepseek/deepseek-chat
DEEPSEEK_API_KEY=sk-...
```

Use any LiteLLM-supported provider by changing `AI_MODEL`/`AI_NAME` and setting the provider-specific API key expected by LiteLLM.

Core endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/ai/process` | Analyze or modify a raster/vector target |
| `GET` | `/ai/functions?format=openai` | Return callable tools in OpenAI tool schema format |
| `GET` | `/ai/functions?format=catalog` | Return a readable function catalog |
| `POST` | `/ai/functions/invoke` | Invoke a registered algorithm function directly |

`/ai/process` accepts `target_id`, `data_type` (`raster` or `vector`), `mode` (`analyze` or `modify`), `language`, `user_prompt`, optional `overwrite`, optional `session_id`, and optional `map_context`.

In modify mode, the Pydantic layer only accepts currently modifiable fields such as raster/vector `name`; read-only spatial statistics and metadata are not written back from model output.

Registered AI-callable functions include spectral indices, raster calculator, vegetation/water/building/cloud extraction, raster/vector clipping, and change detection.

## API Quick Reference

Data service (`:8002`):

- `POST /upload`
- `GET /list`
- `DELETE /raster/{raster_id}`
- `POST /merge-bands`
- `POST /extract-bands`
- `POST /calculate-ndvi`, `/calculate-ndwi`, `/calculate-ndbi`, `/calculate-mndwi`
- `POST /extract-vegetation`, `/extract-water`, `/extract-buildings`, `/extract-clouds`
- `POST /clip-raster-by-vector`
- `POST /raster-calculator`
- `GET /raster/{raster_id}/statistics`
- `GET /raster/{raster_id}/spectrum`
- `POST /execute-script`
- `POST /change/band-diff`, `/change/band-ratio`, `/change/index-diff`
- `POST /rasterize/layer-to-raster`

Annotation service (`:8001`):

- `POST /projects`, `GET /projects`, `DELETE /projects`
- `POST /projects/{project_id}/layers`, `GET /projects/{project_id}/layers`
- `POST /layers/{layer_id}/features`, `GET /layers/{layer_id}/features`
- `GET/PATCH/DELETE /features/{feature_id}`
- `POST /layers/{layer_id}/bulk`
- `GET/POST/PATCH/DELETE /layers/{layer_id}/fields`
- `POST /spatial/clip-vector-by-raster`

Tile services:

- `GET :8005/tile/{index_id}/{z}/{x}/{y}.png?bands=1,2,3`
- `GET :8003/tiles/{layer_id}/{z}/{x}/{y}.pbf`

Executor service (`:8004`):

- `POST /execute`
- `GET /health`

## Optional Worker Cluster

`worker_cluster` contains Celery tasks for offline raster/vector jobs. It is implemented, but most current `data_service` routes still call processing functions synchronously, so the worker is an optional integration path rather than the default product path.

Start a worker after RabbitMQ and Redis are running:

```powershell
celery -A worker_cluster.app.celery_app worker --loglevel=info --concurrency=4 -Q preprocess,index,export
```

See `worker_cluster/README.md` for task names, producer examples, Redis status tracking, and the recommended integration path.

## Testing

Python unit tests:

```powershell
python -m pytest tests/unit/functions
python -m pytest tests/unit/services
```

Benchmarks are opt-in:

```powershell
$env:RS_RUN_BENCHMARKS = "1"
python -m pytest tests/benchmark -m benchmark
```

Frontend tests are configured in `vitest.config.js`, but the frontend package manifests in this revision are empty. Restore or add the required JS dependencies and scripts before running Vitest.

## Screenshots

### Raster Rendering

![Raster rendering](resources/5_1.png)

### Vector Annotation

![Vector annotation](resources/5_2.png)

### AI Analyze Mode

![AI analyze](resources/5_4_1.png)

### AI Modify Mode

![AI modify](resources/5_4_2.png)

### Map Export

![Map export](resources/8_1.png)

## Current Caveats

- Some older comments and docs in the repository are mojibaked. This README is ASCII-only to avoid adding more encoding damage.
- `client/package.json`, `client/packages/app/package.json`, `client/packages/core/package.json`, and `client/pnpm_workspace.yaml` are empty placeholders in this revision.
- The helper start scripts under `services/` are not the most reliable source of truth. Prefer the explicit `uvicorn` commands above while developing.
- `worker_cluster` is optional until the synchronous `data_service` processing paths are replaced with Celery submissions.
- Do not commit real `.env` API keys.

## License

MIT. See `LICENSE`.
