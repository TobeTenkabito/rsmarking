# RSMarking Test Specification

## Purpose

RSMarking is a layered remote-sensing annotation platform. Tests should protect the contracts between the browser UI, FastAPI services, raster/vector storage, and the algorithm library in `functions/implement`.

The primary quality goals are:

- Raster algorithms return stable numeric results for normalized, 8-bit, 16-bit, and nodata-like inputs.
- Raster file operations preserve georeferencing, band count, dtype, and pixel values.
- Tile rendering remains fast enough for interactive map use.
- API services fail with explicit JSON errors and do not touch production storage during tests.
- Client modules keep interaction state at the smallest expected scope: mode, tool, then action.

## Test Layers

### Unit: `tests/unit/functions`

Scope:

- `spectral_indices.py`
- `extraction/*`
- `manipulation.py`
- `rasterize_ops.py`
- small pure helpers from `io_ops.py` where GDAL can be mocked

Rules:

- Use deterministic NumPy arrays.
- Assert output dtype and shape, not just truthiness.
- Keep arrays small unless the test is explicitly marked `benchmark`.
- Avoid real network, database, Docker, or service startup.

### Unit: `tests/unit/client`

Scope:

- Store state transitions.
- Annotation action/tool/mode behavior.
- Small module helpers that can run in jsdom.

Rules:

- Use Vitest and the aliases in `vitest.config.js`.
- Mock Leaflet and service APIs unless the test is in `tests/e2e`.
- Keep DOM assertions focused on visible user behavior.

### Integration: `tests/integration`

Scope:

- FastAPI router contracts.
- Data-service processor flows that create temporary rasters.
- Annotation-service CRUD against an isolated test database.

Rules:

- Mark with `@pytest.mark.integration`.
- Use temporary directories and test-only database URLs.
- Never require production `.env` values.

### E2E: `tests/e2e`

Scope:

- Upload/open raster.
- Create vector project/layer.
- Draw, undo, save, edit attributes.
- Run extraction and load generated mask.
- Export map view.

Rules:

- Use Playwright.
- Seed tiny fixtures from `tests/fixtures`.
- Prefer one happy path plus one recovery path per workflow.

### Benchmarks: `tests/benchmark`

Scope:

- Spectral indices over realistic raster sizes.
- Extraction masks for vegetation, water, building, and cloud.
- Raster IO operations on temporary GeoTIFFs.
- Tile rendering latency and scaling.

Rules:

- Mark with `@pytest.mark.benchmark`.
- Keep default benchmark arrays moderate.
- Set `RS_RUN_BENCHMARKS=1` to enable benchmark execution.
- Report milliseconds per operation and assert loose ceilings to catch severe regressions.

## Required Coverage Matrix

| Area | Required tests |
|---|---|
| Spectral indices | NDVI, NDWI, NDBI, MNDWI, divide-by-zero handling |
| Extraction | vegetation, water MNDWI/Otsu, building NDBI/IBI/score, cloud threshold/Fmask/cirrus |
| Raster operations | extract bands, merge bands, rasterize vector geometries |
| IO | overview success/failure behavior, COG conversion mocked or fixture based |
| Tile engine | blank tile returns `None`, binary mask alpha, multiband RGBA shape, band/tile scaling benchmark |
| Data service | extraction route validates band ids and writes uint8 mask |
| Annotation | draw cancel scopes, feature CRUD, field CRUD |
| Client attribute table | edit cell, add/delete field, CSV export shape |
| Export | PNG/JPEG/SVG option handling and filename behavior |

## Commands

Run Python unit tests:

```bash
python -m pytest tests/unit/functions
```

Run service tests:

```bash
python -m pytest tests/unit/services
```

Run benchmarks:

```bash
$env:RS_RUN_BENCHMARKS="1"
python -m pytest tests/benchmark -m benchmark
```

Run client tests:

```bash
npm run test -- --config vitest.config.js
```
