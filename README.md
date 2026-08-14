# WildfireWatch

Satellite-based burned-area detection pipeline. Ingests real Sentinel-2 imagery, computes
vegetation/burn indices (NDVI, NBR, dNBR), vectorizes burn-severity polygons, stores them in
PostGIS, and serves/visualizes them via FastAPI + a React/MapLibre map.

```
Earth Search STAC (public Sentinel-2 COGs)
        |
        v
  wfw ingest  --(window-read AOI bands)-->  MinIO (raw) + PostGIS (scene metadata)
        |
        v
  wfw process --(NDVI/NBR/dNBR + vectorize)-->  MinIO (processed rasters) + PostGIS (detections)
        |
        v
   FastAPI  --(GeoJSON)-->  React + MapLibre dashboard
```

## Why burned-area mapping, not raw "fire detection"

Sentinel-2 has no thermal band, so this pipeline uses the standard EO technique for mapping
fire impact: **NBR** (Normalized Burn Ratio) computed from NIR/SWIR2, compared between a
pre-fire and post-fire scene to get **dNBR**, thresholded into low/moderate/high severity
burn polygons. This is the same method used operationally for post-fire damage assessment.

## Stack

- **Ingestion**: `pystac-client` against [Earth Search](https://earth-search.aws.element84.com/v1)
  (public, no auth) + `rasterio` windowed reads (`/vsicurl/`) so only the AOI is downloaded.
- **Processing**: `rasterio` + `numpy` for NDVI/NBR/dNBR; `rasterio.features` for vectorizing
  burn masks into severity polygons with area/mean-dNBR stats.
- **Storage**: MinIO (S3-compatible) for rasters, PostgreSQL + PostGIS for metadata/detections.
- **API**: FastAPI + SQLAlchemy/GeoAlchemy2, GeoJSON responses.
- **Frontend**: Vite + React + MapLibre GL.

## Quickstart

```bash
docker compose up -d postgres minio minio-init
cp .env.example .env   # already done if you're continuing this session

pip install -e ".[dev]"
alembic upgrade head    # after first: alembic revision --autogenerate -m "init"

# ingest a pre-fire and a post-fire scene over the same AOI
wfw ingest --bbox 27.9 36.0 28.2 36.3 --start 2023-07-01 --end 2023-07-20 --limit 1
wfw ingest --bbox 27.9 36.0 28.2 36.3 --start 2023-07-25 --end 2023-08-05 --limit 1

# compute dNBR + burn-severity polygons between the two (use the scene ids printed above)
wfw process --pre-scene-id <pre-uuid> --post-scene-id <post-uuid>

uvicorn wildfirewatch.api.main:app --reload   # http://localhost:8000/detections
```

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

Demo AOI used for validation: Rhodes, Greece — July 2023 wildfires (well-documented event
with clean before/after Sentinel-2 coverage). Any bbox/date range works.

## Tests

```bash
pytest -v            # index math + burn-vectorization run standalone
                      # API tests additionally require: docker compose up -d postgres
ruff check src tests
```

CI (`.github/workflows/ci.yml`) runs both against a PostGIS service container, plus a
frontend type-check/build.

## Design notes

Pipeline steps are plain CLI commands (`wfw ingest`, `wfw process`) rather than baked into a
scheduler — each one is a pure function of its inputs/outputs (STAC query → MinIO + DB row;
scene pair → MinIO + DB rows), so each becomes a single Airflow task or Kubernetes Job without
a rewrite.

## Roadmap (not built in this pass)

- **Orchestration**: Airflow DAG wrapping `ingest` → `process` → notify, scheduled per AOI.
- **Kubernetes**: Deployments for the API, CronJob/Job for ingestion+processing workers,
  ConfigMaps/Secrets for config, PVC-backed or cloud object storage.
- **AWS**: S3 for raw/processed buckets, EKS for the K8s workloads, RDS PostgreSQL (PostGIS
  extension) for the database, CloudWatch for logs/metrics.
- **Observability**: structured logging, Prometheus metrics (images processed, processing
  duration, failed jobs), Grafana dashboards.
