# RSMarking

RSMarking is a remote-sensing annotation and raster analysis workspace. It combines a Leaflet/Cesium browser map, FastAPI microservices, PostGIS-backed vector storage, GDAL/rasterio processing, a permission-aware AI agent, and an optional Celery worker layer for longer-running jobs.

The repository is currently most useful as a local development stack for GeoTIFF upload, raster metadata management, on-the-fly map tiles, vector annotation, raster/vector analysis tools, AI-assisted project operations, and Docker-isolated custom Python scripts.

> Updated against the current working tree on 2026-11-12. Screenshots below were captured from this version. The PowerShell launcher, service entry points, `.env.example`, and tests remain the operational sources of truth.

[Quick start](#quick-start) · [Screenshots](#screenshots) · [AI configuration](#ai-gateway-configuration) · [Agent workspace](#agent-workspace) · [Testing](#testing)

## Features

- Browser map client with synchronized Leaflet and Cesium 2D/3D viewing, including antimeridian, polar, and repeated-world geometry normalization.
- Chinese, English, Japanese, and Spanish interface and AI response languages.
- GeoTIFF metadata ingestion with raw and COG storage directories.
- On-the-fly raster tile rendering with bounded requests, L1/L2 caching, concurrent-miss coalescing, HTTP ETags, and optional Cython acceleration.
- Vector projects, layers, features, attribute fields, shapefile import, and PostGIS spatial indexes.
- Vector tile service using PostGIS `ST_AsMVT`.
- Raster algorithms for NDVI, NDWI, NDBI, MNDWI, band extraction, band merge, raster calculator expressions, DEM analysis, Fourier/wavelet/PCA transforms, texture feature extraction, time-series analysis, rasterization, clipping, and change detection.
- Automatic raster acquisition-time extraction and non-blocking time-series discovery with provenance, confidence, grid alignment, and documented fallbacks for undated imagery.
- Extraction algorithms for vegetation, water, buildings, and clouds.
- AI gateway built around LiteLLM with multiple provider routes, analyze/modify modes, and bounded planning, execution, independent acceptance, and repair agents.
- Agent workspace with Markdown, configurable send shortcuts, visible conversation history, editable titles and notes, pinning, chat import/export, branching, and live task progress.
- Durable session checkpoints, scoped derived-task authorization, recoverable script references, and shared model/tool/token budgets.
- Docker-isolated Python script executor with validated raster/vector inputs, GeoTIFF or GeoJSON outputs, bounded logs, resource limits, and restricted host-path access.
- Optional Celery worker cluster for offline preprocessing, index calculation, and GeoJSON export jobs.

## Documentation

| Guide | Contents |
|---|---|
| [AI provider setup](docs/ai-providers.md) | Model routing, provider-specific configuration, reasoning settings, and troubleshooting |
| [Environment examples](.env.example) | Copyable provider blocks and service/runtime settings; never put real credentials in this file |
| [Agent workspace](docs/agent-workspace.md) | Conversation controls, collaboration, permissions, context recovery, and limits |
| [Real-model coastline validation](docs/agent-coastline-validation-2026-11-12.md) | Observed results, failure cases, fixes, API consumption, and incomplete final acceptance |
| [Worker cluster](worker_cluster/README.md) | Background jobs, queues, deployment, and status tracking |

## Agent Workspace

The default Agent mode separates planning, execution, and acceptance. The planner inspects available inputs and assigns concrete subtasks; execution agents receive only their assigned tools; an independent read-only verifier checks actual outputs. Rejected outputs return to the planner for bounded repair. The settings panel also offers direct execution for simpler workflows.

- **Conversation UI:** GFM Markdown, tables and code blocks; Enter to send and Ctrl/Command + Enter for a new line, with the inverse mode available. Shift + Enter inserts a new line, and IME composition does not send a message.
- **Visible history:** left sidebar, editable titles, smaller notes beneath titles, expandable note text, pinning, search, automatic saving, JSON import/export, and branching from a message or conversation.
- **Progress:** current planning/execution/review/repair phase, tool, task progress, and elapsed time. Progress displays operational status, not private model reasoning.
- **Continuation:** persistent checkpoints and session-scoped references retain messages, attachments, tool observations, and sandbox scripts. Interrupted requests can resume without blindly repeating successful writes.
- **Outputs:** downloadable documents, tables, images, and sandbox-generated GeoJSON. Vector acceptance tools inspect saved geometry and can sample actual raster pixels on either side of a line.
- **Write back to the workspace:** `import_generated_artifact` registers saved GeoJSON as a new vector layer or georeferenced GeoTIFF as imagery. It also accepts small JSON FeatureCollections generated directly by the Agent, preserves original files, and reuses repeated imports. Imported data is selected on the map automatically.
- **Environment settings:** the circular gear button at the bottom left opens provider, model, API address, and key settings. Changes apply to subsequent AI requests; restore `.env` defaults at any time. See [configuration and local access details](docs/ai-providers.md#在界面设置环境).

Default collaborative limits are 6 logical agents, 1 repair round, 24 model calls, 12 tool calls, and a cumulative token budget of 300,000. Calls reserve a conservative estimate before execution; valid provider usage settles that reserve afterwards. Missing usage and timeouts retain the reserve. These limits bound work rather than guarantee completion or a particular bill.

The real-model coastline test produced candidate line geometry and verified derived-task authorization, empty-output rejection, and replanning. **Its final model acceptance handoff did not complete within the cumulative budget.** Geometry checks and spectral samples are not ground-truth accuracy measurements. See the [validation report](docs/agent-coastline-validation-2026-11-12.md) for the exact scope and limitations.

## Frontend Tool Placement Standards

RSMarking separates raster workflows between the main **Imagery Processing Center** and each raster row's hidden **RASTER FUNCTIONS** menu.

Use **Imagery Processing Center** for reusable processing workflows that can be started without first opening a specific raster row. A tool belongs here when it creates a derived raster/vector product, changes raster geometry or radiometry, combines multiple inputs, runs a classification or extraction algorithm, or opens a full workflow modal with its own source-raster selector and parameters.

Current Processing Center groups:

| Group | Tools |
|---|---|
| DEM Analysis | Elevation, slope, aspect, hillshade/shading, curvature, topographic relief, topographic humidity index, flow direction, flow accumulation, watershed delineation |
| Transform Analysis | Fourier analysis, wavelet analysis, PCA |
| Texture Features | GLCM, local statistics window, Gabor filtering, LBP |
| Time-Series Analysis | Monthly compositing, annual compositing, maximum value compositing, median compositing, moving window smoothing, Savitzky-Golay filtering, trend analysis, seasonality analysis, phenological parameter extraction |
| Band Processing | Band merge, band extraction, resampling |
| Preprocessing | Radiometric calibration, geometric correction |
| Index Calculation | NDVI, NDWI, NDBI, MNDWI |
| Feature Extraction | Vegetation, water, building, cloud extraction |
| Classification | Supervised classification, unsupervised classification, deep learning segmentation |
| Raster Calculator | General raster calculator |
| Script Programming | Python script editor |
| Change Detection | Band difference, ratio, and index-difference workflows |
| Format Conversion | Vector-to-raster and raster-to-vector conversion |

Use **RASTER FUNCTIONS** for row-context actions on the exact raster item the user opened. A tool belongs here when it inspects, manages, or edits metadata for that one raster and does not represent a general algorithm workflow. These actions may use the raster row as their only context and should remain quick, local, and non-discoverability-critical.

Current RASTER FUNCTIONS actions:

| Action | Reason |
|---|---|
| Spectral Profile | Starts map inspection for the selected raster |
| Raster Statistics | Opens descriptive statistics for the selected raster |
| Attribute Table | Manages metadata/fields attached to the selected raster |
| Remove Raster | Deletes the selected raster item |

When adding a new tool, place it in **Imagery Processing Center** by default if it produces a new analytical output or needs a parameter form. Place it in **RASTER FUNCTIONS** only when the action is fundamentally tied to the opened raster row and is primarily inspect/manage/delete behavior. If a Processing Center workflow benefits from a selected raster shortcut, pass that raster into the modal as a preselected source rather than duplicating the workflow in RASTER FUNCTIONS.

## Destructive raster administration

Bulk raster clearing is disabled by default. To enable it, set
`RS_ENABLE_ADMIN_OPERATIONS=true` and a private, random `RS_ADMIN_TOKEN` in `.env`
or the data-service environment, then restart the service. The browser asks for
this token when clearing data; it is not saved in browser storage or frontend configuration.

The endpoint is `POST /admin/rasters/clear`, with `Authorization: Bearer <token>`
and JSON body `{"confirmation":"DELETE_ALL_RASTERS"}`. The old
`GET /debug/clear-db` endpoint has been removed. Raster deletion commits metadata
first and only removes managed raw/COG files that no remaining raster references.
Filesystem cleanup failures are logged and leave orphaned files for later cleanup.

## Shapefile import limits

Shapefile imports accept one dataset with `.shp`, `.shx`, `.dbf` and optional
`.prj`/`.cpg` components, up to 64 MiB combined and 100,000 features. Oversized
imports return HTTP 413. The annotation service also bounds the streamed
multipart request body before upload spooling. ZIP parsing applies the same
decompressed-size limit and accepts at most 100 archive members.

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
| Docker sandbox       |      | LiteLLM + policy gate |
+----------------------+      +-----------------------+

PostgreSQL/PostGIS, Redis, and RabbitMQ are provided by infrastructure/docker/docker-compose.yml.
The Compose file provides infrastructure; the launcher starts the application services on the host.
worker_cluster is optional and consumes RabbitMQ tasks while reporting status through Redis.
```

## Repository Map

```text
client/                         Static browser client
  index.html                    Main app shell
  packages/app/src/             App modules, API adapters, state, i18n
  packages/core/src/map.js      Leaflet/Cesium map engine
  packages/core/src/geo/geometryRender.js
                                Shared 2D/3D geometry normalization
  packages/ui/src/              Modal and sidebar templates/components

services/
  annotation_service/           Vector projects, layers, features, fields
  data_service/                 Raster metadata, uploads, algorithms, bridges
  tile_service/                 Raster tile engine and Cython extensions
  vtile_service/                PostGIS vector tile endpoint
  executor_service/             Docker sandbox for custom Python scripts
  ai_gateway/                   AI gateway, collaboration, policy, checkpoints, and tool registry

functions/
  implement/                    Core raster, vector, index, extraction algorithms
  common/                       Shared helpers such as Snowflake-style IDs

worker_cluster/                 Optional Celery worker layer
infrastructure/docker/          PostgreSQL/PostGIS, RabbitMQ, Redis compose file
infrastructure/*_migrations/    Alembic migrations for raster and vector DBs
storage/raw/                    Uploaded/original rasters and script outputs
storage/cog/                    Cloud-optimized GeoTIFF outputs
storage/ai_artifacts/            Downloadable AI-generated files
storage/ai_agent_state.sqlite3   Durable agent context and operation journal
docs/                           Configuration, workspace, and validation guides
tests/                          Pytest, Vitest, Playwright, and benchmark tests
resources/screenshots/          Versioned screenshots used by this README
```

## Services

| Service | Port | Entry point | Main responsibility |
|---|---:|---|---|
| Annotation service | 8001 | `services.annotation_service.main:app` | Projects, layers, vector features, fields, shapefile import |
| Data service | 8002 | `services.data_service.main:app` | Raster metadata, uploads, spectral indices, extraction, clipping, scripts |
| Vector tile service | 8003 | `services.vtile_service.main:app` | MVT tiles from PostGIS |
| Executor service | 8004 | `services.executor_service.main:app` | Docker-isolated Python script execution |
| Tile service | 8005 | `services.tile_service.main:app` | Cached RasterIO XYZ PNG rendering and HTTP revalidation |
| AI gateway | 8006 | `services.ai_gateway.main:app` | Analyze/modify, agent collaboration and progress, conversations, artifacts, and tool authorization |

## Rendering Architecture

### Browser 2D/3D rendering

Source GeoJSON remains unchanged in application state. Before display, the shared geometry pipeline unwraps longitudes, splits antimeridian and polar crossings, and generates renderer-specific copies for Leaflet and Cesium. This prevents a 2D/3D switch from feeding one renderer's clipped coordinates back into the other and supports features that cross the dateline or wrap around the globe more than once.

Raster layers use the tile service below in both modes. The map engine reconciles renderer state when switching modes; it does not change raster pixels or source metadata.

### Raster tile request path

```text
GET /tile/{index_id}/{z}/{x}/{y}.png
  -> validate XYZ and requested bands
  -> resolve the current raster path/version
  -> run blocking cache, RasterIO, and PNG work in a worker thread
  -> coalesce concurrent misses for the same tile
  -> L1 memory cache / L2 disk cache
  -> CRS-aware RasterIO masked window read and resampling
  -> stretch + RGBA render + PNG encode
  -> ETag and Cache-Control response
```

The source file modification time and size are part of the internal cache key, so a replaced raster does not reuse an old rendered tile. Browser/proxy revalidation uses a content-derived ETag. Missing files return a transparent tile with `Cache-Control: no-store`.

The tile service loads compiled Cython rendering helpers when the local extension is available and otherwise uses the NumPy implementation. `GET :8005/health` reports the active renderer instead of assuming acceleration.

To rebuild the optional extension for the active Python environment:

```powershell
cd services/tile_service
python setup.py build_ext --inplace
cd ../..
```

Important tile settings (all optional):

| Setting | Default | Purpose |
|---|---:|---|
| `TILE_MAX_BANDS` | `4` | Bounds client-controlled RasterIO and render work |
| `TILE_MAX_ZOOM` | `24` | Rejects invalid or unreasonable XYZ requests |
| `TILE_RASTER_OPEN_MODE` | `per_request` | Uses isolated RasterIO handles; `thread_local` is an opt-in reuse mode |
| `TILE_RESAMPLING_MODE` | `quality` | Selects the configured resampling policy |
| `TILE_ALPHA_MODE` | `auto` | Chooses data/mask alpha behavior |
| `TILE_PNG_COMPRESS_LEVEL` | `1` | Balances PNG CPU cost and response size |
| `TILE_HTTP_CACHE_MAX_AGE_SECONDS` | `60` | Browser/proxy freshness lifetime |
| `TILE_HTTP_CACHE_STALE_WHILE_REVALIDATE_SECONDS` | `300` | Allows stale tiles during background revalidation |
| `TILE_PROFILE` | `false` | Logs per-stage tile timing for diagnosis |

See `.env.example` for path-cache and engine-cache controls. Keep `per_request` for general development; use `thread_local` only after representative load testing because RasterIO dataset handles are thread-affine.

## Temporal Metadata and Time-Series Analysis

RSMarking stores acquisition time separately from upload time. `created_at` only records when a raster entered the project and is never treated as an observation date.

During upload, temporal metadata is resolved automatically in confidence order:

```text
STAC / Landsat MTL / Sentinel SAFE
  -> raster and GDAL metadata tags
  -> sensor-specific standard filename
  -> generic full-date filename
  -> unknown
```

The raster record stores `acquired_at`, its source and confidence, optional acquisition end time, platform, sensor, product ID, processing level, and tile ID. Legacy rows are enriched lazily the first time they participate in time-series analysis. No confirmation dialog is required; expert corrections remain available through `PATCH /raster/{raster_id}/temporal-metadata`.

`GET /time-series-candidates` groups and chronologically sorts compatible rasters automatically. Grouping uses platform, sensor, processing level, tile ID, band count, and spatial coverage; when tile metadata is absent, spatial coverage prevents unrelated regions with otherwise similar rasters from being merged. Candidate responses include date coverage, metadata-source counts, duplicate-date warnings, automatic-alignment requirements, and suggested operations. The browser initially selects the largest compatible candidate instead of treating every project raster as one series.

Missing dates use operation-specific, visible fallbacks:

| Operation | Automatic behavior when dates are missing |
|---|---|
| Maximum/median composite | Runs normally; calendar dates are not required |
| Monthly/annual composite | Uses dated rasters and skips only undated inputs |
| Moving-window/Savitzky-Golay | Uses ordered observation steps and warns about incomplete or irregular cadence |
| Trend | Uses elapsed days when the date axis is complete and distinct; otherwise reports slope per observation step |
| Seasonality/phenology | Reports day-of-year with complete dates; otherwise reports observation positions |

Different but georeferenced grids are aligned to the first selected raster with mask-aware RasterIO reprojection. Results return `temporal_axis`, `date_coverage`, `date_sources`, `aligned_input_count`, and non-blocking `warnings`, and write temporal provenance tags into the output GeoTIFF.

## Prerequisites

- Docker Desktop or Docker Engine with Compose.
- Conda or Mamba.
- Python 3.12. The checked-in `environment.yml` creates a Python 3.12 environment named `rsmarking`.
- A browser. The frontend is currently a static app, so there is no `npm run dev` workflow in this revision.
- Optional: Node.js for Vitest and Playwright tests. The checked-in browser-test configuration uses Microsoft Edge in headless mode.

## Quick Start

From the repository root:

For a first-time setup, create the Python environment and a local configuration file before using either launch method:

```powershell
conda env create -f environment.yml
conda activate rsmarking
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Review `.env` for your database and service settings. AI features additionally require a compatible model and provider credentials; map browsing and ordinary processing do not require a model API key. Keep credentials in the server environment or ignored `.env`, never in `client/runtime-config.js`.

### One-click Windows launch

Double-click `rsmarking.exe` when it has been built, double-click
`launch_rsmarking.bat`, or run:

```powershell
.\launch_rsmarking.ps1
```

The launcher starts Docker Desktop when it can find it, runs `docker compose up -d`,
prepares databases/extensions, runs migrations, writes the frontend runtime
configuration, starts the Celery worker, starts all six FastAPI services,
checks that the frontend is reachable, writes logs to `logs/launch`, and opens:

```text
http://localhost:8002/client/index.html
```

Stop the launched processes with:

```powershell
.\stop_rsmarking.ps1
```

If the executable wrapper has been rebuilt, you can also stop without an
interactive pause by double-clicking `rsmarking-stop.exe` or running:

```powershell
.\rsmarking.exe --stop
```

Useful options:

```powershell
.\launch_rsmarking.ps1 -Reload
.\launch_rsmarking.ps1 -AllowInlineFallback
.\launch_rsmarking.ps1 -NoBrowser
.\launch_rsmarking.ps1 -RequireExecutorImage
.\stop_rsmarking.ps1 -StopDocker
```

The executable is intentionally a thin wrapper over the PowerShell scripts, so
the PowerShell launch/stop scripts remain the source of truth. It forwards
startup arguments to `launch_rsmarking.ps1`, for example:

Keep `rsmarking.exe` in the repository root. At runtime it enters that folder
and starts `.\launch_rsmarking.bat` with relative paths.

```powershell
.\rsmarking.exe -NoBrowser -AllowInlineFallback
```

Build or rebuild the executable from the repository root with:

```powershell
.\tools\build_rsmarking_exe.ps1
```

The build script uses the `rsmarking` Conda environment when available and
installs PyInstaller into that environment if it is missing. The outputs are
written to `.\rsmarking.exe` and `.\rsmarking-stop.exe`.

The script uses the active `python` when it has the required packages; if not,
it tries `conda run -n rsmarking python`.

The executor sandbox image is built automatically when missing. If Docker Hub
or the base image pull is unavailable, the launcher warns and continues so the
frontend and normal backend workflows still start; use `-RequireExecutorImage`
when custom script execution must be available before startup is considered
successful.

Custom scripts receive selected raster inputs as `input_0`, `input_1`, and
stable `raster_<index_id>` aliases. A map-selected vector feature is copied
into the isolated container as real GeoJSON and exposed as `feature_0`,
`features`, and `feature_by_id`; helpers include `feature_geometry()`,
`feature_shape()`, and `read_geojson()`. Scripts that only inspect or calculate
vector data may finish without creating a raster, in which case their bounded
execution log is shown in the script editor. Raster-producing scripts should
write `OUTPUT_FILE`. The Agent's `run_script_sandbox` tool also supports
`output_format="geojson"`: write a WGS84 FeatureCollection to `OUTPUT_FILE` using
`json.dump` and `sandbox_open`. The gateway saves the actual coordinates and
returns a download link, without copying geometry through model text.

Host raster paths are accepted only from the repository `storage` directory by
default. Deployments with additional managed data roots can set
`SANDBOX_ALLOWED_INPUT_ROOTS` using the platform path separator.

### Manual launch

Use the `rsmarking` environment prepared above and run commands from the repository root.

Start infrastructure:

```powershell
cd infrastructure/docker
docker compose up -d
cd ../..
```

This Compose stack starts PostgreSQL/PostGIS, RabbitMQ, and Redis only. Start the six FastAPI application services separately with the commands below, or use the one-click launcher.

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

For a separate frontend origin or non-default ports, set the service URLs in `client/runtime-config.js`; the launcher generates this file for its configured ports. Restart the relevant backend after changing server-side environment variables.

## AI Gateway Configuration

Use the circular **Agent environment** button for local configuration without editing `.env`. The saved server configuration takes precedence for subsequent chat requests and never exposes its key in a settings response. The settings interface is limited to localhost access; running tasks retain their original provider settings. `.env` remains available as the fallback. The ignored `storage/ai_environment.json` file contains the saved key and must be protected with local filesystem permissions.

The AI gateway loads `.env` from the repository root and calls LiteLLM. A minimal DeepSeek-style configuration looks like this:

```env
AI_MODEL=deepseek/deepseek-chat
DEEPSEEK_API_KEY=your_deepseek_api_key
AI_TIMEOUT=90000
AI_MAX_TOKENS=4096
```

Choose a provider from [the supported configurations](docs/ai-providers.md) by changing `AI_MODEL` and its provider-specific key. OpenAI-compatible gateways use `openai/<model-id>` and their own Base URL. `AI_NAME` and `AI_MODEL_NAME` remain compatibility fallbacks; `AI_MODEL` is preferred.

The repository-root `.env` is loaded independently of the launch directory; existing process environment variables take precedence. `AI_TIMEOUT` is in milliseconds. Tool calling support depends on the configured model and endpoint: provider routing alone does not make a text-only or Responses-only endpoint compatible with the current Chat Completions agent.

Some OpenAI-compatible configurations reject tool requests with a non-`none` reasoning effort. When the endpoint explicitly requires it, set `AI_TOOL_REASONING_EFFORT=none` to override only OpenAI-routed tool requests; ordinary requests retain `AI_REASONING_EFFORT`. This is an explicit compatibility setting, not an automatic retry or a universal provider requirement.

Inspect resolved configuration without making a model request or printing the key:

```powershell
python -m services.ai_gateway.diagnose
```

The agent can create persistent downloadable documents, SVG images, and CSV/XLSX/JSON tables. To enable provider-backed raster image generation as well, configure a LiteLLM-compatible image model separately:

```env
AI_IMAGE_MODEL=openai/gpt-image-1
OPENAI_API_KEY=your_openai_api_key
```

Generated files are stored under `storage/ai_artifacts` by default; override that location with `AI_ARTIFACT_DIR`.

Core endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/ai/process` | Analyze or modify a raster/vector target |
| `GET` | `/ai/functions?format=openai` | Return callable tools in OpenAI tool schema format |
| `GET` | `/ai/functions?format=catalog` | Return a readable function catalog |
| `POST` | `/ai/functions/invoke` | Invoke a registered algorithm function directly |
| `POST` | `/ai/agent` | Run the permission-aware tool-using agent |
| `GET` | `/ai/agent/{session_id}/progress?request_id=...` | Read operational progress for one request |
| `GET/POST/DELETE` | `/ai/conversations` | List, save, or clear archived agent conversations |
| `GET/DELETE` | `/ai/conversations/{archive_id}` | Read or delete one archived conversation |
| `PATCH` | `/ai/conversations/{archive_id}` | Edit a title and note |
| `PATCH` | `/ai/conversations/{archive_id}/pin` | Pin or unpin a conversation |
| `POST` | `/ai/conversations/import` | Import a conversation into a new session |
| `GET` | `/ai/conversations/{archive_id}/export` | Export conversation JSON |
| `POST` | `/ai/conversations/{archive_id}/branch` | Branch a whole conversation or a message prefix |
| `POST` | `/ai/conversations/{archive_id}/restore` | Restore an archive into an agent session |
| `GET` | `/ai/artifacts/{artifact_id}` | Preview an AI-generated image artifact |
| `GET` | `/ai/artifacts/{artifact_id}/download` | Export an AI-generated artifact |

`/ai/process` accepts `target_id`, `data_type` (`raster` or `vector`), `mode` (`analyze` or `modify`), `language`, `user_prompt`, optional `overwrite`, optional `session_id`, and optional `map_context`.

In modify mode, the Pydantic layer only accepts currently modifiable fields such as raster/vector `name`; read-only spatial statistics and metadata are not written back from model output.

Registered AI-callable functions include downloadable document/table generation, optional AI image generation, raster discovery/metadata/statistics/spectrum and field management, processing-status lookup, spectral indices, raster calculator, DEM analysis, Fourier/wavelet/PCA transforms, texture feature extraction, time-series analysis, vegetation/water/building/cloud extraction, raster/vector clipping, and change detection.

`/ai/agent` accepts `user_prompt`, `language`, optional `target_id` plus `data_type`, optional `map_context`, `session_id`, `request_id`, `tool_names`, bounded `attachments`, `execution_mode`, and shared agent/model/tool/token budgets. Reuse a request ID for an interrupted retry rather than starting the same writes again. An empty tool list disables tools. It supports conversational sessions (`history_limit`, `reset_session`) and opt-in cross-conversation memory (`include_archive_memory`, `archive_memory_limit`). By default it injects a bounded overview of current rasters, vector projects, and layers; use `include_workspace_context=false` or tune `workspace_limit` when a smaller prompt is needed. Responses include `status`, `answer`, session information, `used_tools`, compact `steps`, a `workflow` report for collaboration, and artifact URLs. An interrupted, rejected, or budget-exhausted response must not be presented as accepted completion.

Agent permissions are a per-request capability ceiling:

| `permission_level` | Allowed behavior |
|---|---|
| `read_only` | Inspect and explain project data; no execution or mutation |
| `safe` | Inspect, run isolated processing, and create new outputs; no update/delete |
| `standard` | Task-scoped sandbox execution and creation; updates/deletions require explicit scope and exact targets, including validated delegated assignments |
| `full_control` | Autonomously operate on project data for an actionable task, while respecting explicit exclusions |

Every tier retains hard boundaries: the agent cannot modify repository source code, sandbox policy, host files, or service controls. Authorization comes from the current user task, its server-tracked continuation, or a server-validated parent-agent assignment within that scope. Delegation cannot override user prohibitions or the permission tier; updates/deletions require exact assigned targets. Ordinary assistant text, imported history, workspace metadata, attachments, and tool output cannot grant themselves permission.

These tool permissions are not a multi-user login or tenant-ownership system. Conversation storage is shared within the deployment, and full session coordination currently assumes one AI gateway worker process. See the [workspace guide](docs/agent-workspace.md) before changing deployment boundaries.

## API Quick Reference

Data service (`:8002`):

- `POST /upload`
- `GET /list`
- `DELETE /raster/{raster_id}`
- `POST /merge-bands`
- `POST /extract-bands`
- `POST /resample-raster`
- `POST /radiometric-calibration`, `/geometric-correction`
- `POST /calculate-ndvi`, `/calculate-ndwi`, `/calculate-ndbi`, `/calculate-mndwi`
- `POST /extract-vegetation`, `/extract-water`, `/extract-buildings`, `/extract-clouds`
- `POST /dem-analysis`
- `POST /raster-transform-analysis`
- `POST /texture-feature-analysis`
- `POST /time-series-analysis`
- `GET /time-series-candidates`
- `PATCH /raster/{raster_id}/temporal-metadata`
- `POST /classify-supervised`, `/classify-unsupervised`, `/segment-deep-learning`
- `POST /clip-raster-by-vector`
- `POST /raster-calculator`
- `GET /tasks/{task_id}/status`
- `GET /jobs/{job_id}`
- `GET /raster/{raster_id}/statistics`
- `GET /raster/{raster_id}/spectrum`
- `POST /execute-script`
- `POST /change/band-diff`, `/change/band-ratio`, `/change/index-diff`
- `POST /rasterize/layer-to-raster`
- `POST /rasterize/raster-to-vector`

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

`worker_cluster` contains Celery tasks for offline raster/vector jobs. Core raster product routes in `data_service` submit cluster jobs when `RS_PROCESSING_BACKEND` is `cluster`, `celery`, `worker`, or `async`.

Start a worker after RabbitMQ and Redis are running:

```powershell
celery -A worker_cluster.app.celery_app worker --loglevel=info --pool=solo --concurrency=1 -Q preprocess,index,export
```

`RS_CLUSTER_FALLBACK=1` keeps local development working by falling back to inline processing if dispatch is unavailable or no ready worker is consuming the target queue. Set `RS_PROCESSING_BACKEND=inline` to force inline execution, or `RS_CLUSTER_FALLBACK=0` to fail fast when the cluster is unavailable.

See `worker_cluster/README.md` for task names, producer examples, Redis status tracking, and cluster integration details.

## Testing

Python unit tests:

```powershell
python -m pytest tests/unit/functions
python -m pytest tests/unit/services
python -m pytest tests/unit/services/tile_rendering -m "not benchmark"
```

Service communication tests:

```powershell
python -m pytest tests/integration
```

The bridge tests mock cross-service HTTP calls. To probe a running stack on the six FastAPI service ports, enable the opt-in live checks:

```powershell
$env:RS_RUN_PORT_TESTS = "1"
python -m pytest tests/integration/test_port_communication.py
```

Override a live port target with `RS_PORT_TEST_ANNOTATION_URL`, `RS_PORT_TEST_DATA_URL`, `RS_PORT_TEST_VTILE_URL`, `RS_PORT_TEST_EXECUTOR_URL`, `RS_PORT_TEST_TILE_URL`, or `RS_PORT_TEST_AI_URL`.

Benchmarks are opt-in:

```powershell
$env:RS_RUN_BENCHMARKS = "1"
python -m pytest tests/unit/services/tile_rendering/benchmark -m benchmark
```

Frontend unit tests:

```powershell
npm ci
npm test
npm run test:ui
```

Playwright runs the current UI against isolated fixture APIs and writes screenshots to `test-results/`. It does not read model credentials or spend API credits. Ordinary unit tests use model substitutes; real-provider checks must be deliberately run and budgeted separately. The [2026-11-12 validation report](docs/agent-coastline-validation-2026-11-12.md) records the tested backend/frontend subsets and the real-model outcome rather than implying that every workflow or provider passed online validation.

## Screenshots

Captured on 2026-11-12 from the current application at 1600 × 1000. The map uses the project's Landsat MNDWI imagery and saved candidate coastline GeoJSON. The Agent view replays explicitly labelled local validation results with demonstration history entries; it does not represent a new model request or a completed automatic acceptance. Capture details are in [the screenshot notes](resources/screenshots/2026-11/README.md).

### Raster and Vector Workspace

![Current raster workspace with a saved coastline vector overlay](resources/screenshots/2026-11/map-workspace.png)

### Raster Calculator

![Current raster calculator](resources/screenshots/2026-11/raster-calculator.png)

### Classification Workflow

![Current unsupervised classification configuration](resources/screenshots/2026-11/classification.png)

### Agent Conversations and Markdown

![Current Agent workspace with visible history, notes, pinning and Markdown results](resources/screenshots/2026-11/agent-workspace.png)

### Map Export

![Current map export options](resources/screenshots/2026-11/map-export.png)

## Current Caveats

- Some older comments and auxiliary docs in the repository are mojibaked; edited text files should be kept as UTF-8.
- The frontend does not currently ship a package-managed dev server workflow; use the data-service static mount or another static server while developing the app.
- The infrastructure Compose file does not containerize the six application services.
- The helper start scripts under `services/` are not the most reliable source of truth. Prefer the explicit `uvicorn` commands above while developing.
- The Cython tile renderer is optional. Builds without the extension use the tested NumPy fallback and may have lower throughput.
- `TILE_RASTER_OPEN_MODE=thread_local` trades fewer dataset opens for more lifecycle complexity; benchmark it with the deployment's actual server/thread model before enabling it.
- Very large vector layers are still transferred as GeoJSON in several annotation workflows; the PostGIS MVT service is available, but not every browsing path has migrated to it.
- `worker_cluster` is optional; processing can still run inline according to `RS_PROCESSING_BACKEND` and fallback settings.
- Agent acceptance remains model- and evidence-dependent. Shared budgets may stop a task before completion; provider routing and offline tests do not guarantee online tool support or scientific output quality.
- Agent checkpoints and generated artifacts persist on disk. Include them in storage and backup planning; chat import/export transfers references to generated files, not the files themselves.
- Do not commit real `.env` API keys.

## License

MIT. See `LICENSE`.
