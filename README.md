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
pytest -v                    # index math + burn-vectorization run standalone
                              # API tests additionally require: docker compose up -d postgres
ruff check src tests airflow
```

CI (`.github/workflows/ci.yml`) runs the above against a PostGIS service container, a DAG
import-error check (builds `Dockerfile.airflow` and loads `airflow/dags` with `DagBag`, no live
Airflow DB needed), and a frontend type-check/build.

## Design notes

Pipeline steps are plain CLI commands (`wfw ingest`, `wfw process`) rather than baked into a
scheduler — each one is a pure function of its inputs/outputs (STAC query → MinIO + DB row;
scene pair → MinIO + DB rows), so each becomes a single Airflow task or Kubernetes Job without
a rewrite.

## Orchestration (Airflow)

`airflow/dags/wildfirewatch_dag.py` wraps `wfw ingest` → `wfw process` → notify as a weekly,
per-AOI DAG, without modifying either CLI command:

- `ingest_baseline` / `ingest_current` (`BashOperator`): run `wfw ingest` for a fixed pre-fire
  baseline window and a rolling current window (`lookback_days` ending at the DAG run date).
- `select_scene_pair` (`@task`): queries PostGIS directly for the lowest-cloud-cover baseline
  scene and the newest not-yet-processed current scene; skips the AOI if either is missing.
- `process_pair` (`BashOperator`): runs `wfw process --pre-scene-id ... --post-scene-id ...`
  with the ids selected above.
- `notify` (`@task`): logs a summary if new detections were stored, and POSTs to the Airflow
  Variable `wfw_notify_webhook_url` if one is set.

AOIs come from the Airflow Variable `wfw_aois` (JSON list of `{name, bbox, baseline_start,
baseline_end, max_cloud_cover, lookback_days}`); with no Variable set, it defaults to the
Rhodes demo AOI above.

```bash
docker compose up -d airflow   # http://localhost:8080 (user: admin, password:
                                # `docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated`)
```

Runs with `SequentialExecutor`/SQLite (`airflow standalone`) for local/demo use; a real
deployment would move to `LocalExecutor`/`CeleryExecutor` with a dedicated metadata DB.

## Observability

Structured logging (`structlog`) and Prometheus metrics across the API and the `wfw`
ingest/process CLI:

- **API**: a request-logging middleware plus `prometheus-fastapi-instrumentator` exposing
  `GET /metrics` — it's a long-running process, so Prometheus scrapes it directly.
- **CLI**: `wfw ingest`/`wfw process` are short-lived batch jobs instead, so they push metrics
  (scenes ingested, processing duration/outcome, detections stored) to a Prometheus Pushgateway
  on exit — best-effort, a monitoring outage never fails the pipeline.
- `LOG_FORMAT=json` switches logging from human-readable console output (the default, for local
  runs) to JSON (set by `docker-compose.yml` for the `api`/`airflow` services).

```bash
docker compose up -d prometheus pushgateway grafana
# Prometheus:  http://localhost:9090  (Status > Targets)
# Grafana:     http://localhost:3000  (anonymous viewer access; admin/admin to edit) — the
#              WildfireWatch dashboard is auto-provisioned from monitoring/grafana/
```

## Kubernetes

Plain YAML manifests in `k8s/`, applied in filename order, mapping each existing piece onto
native primitives without changing any application code — the same "pure function of its
inputs/outputs" design that lets `wfw ingest`/`wfw process` become Airflow tasks also lets them
become Kubernetes Jobs:

- `00`–`02`: namespace, ConfigMap, and a Secret **template** (`02-secret.example.yaml` — copy to
  `02-secret.yaml`, fill in real values; that filename is gitignored).
- `03`–`04`: self-hosted `postgres`/`minio`, PVC-backed — for dev/demo clusters. Point
  `DATABASE_URL`/`S3_ENDPOINT_URL` at the Terraform-managed RDS/S3 instead for production, and
  drop these two files.
- `05`: a `migrate` Job (`alembic upgrade head`), run once before rolling out `api`.
- `06`: the `api` Deployment (2 replicas) + Service.
- `07`: `ingest-rhodes-greece`, a weekly CronJob running `wfw ingest` for the demo AOI over a
  rolling window.
- `08`: a `process` Job **template** — `wfw process` needs a specific pre/post scene pair, and
  picking that pair is exactly the DB-query logic in `select_scene_pair` (see Airflow, above),
  so this isn't a blind CronJob. Submit it with real ids:
  `PRE_SCENE_ID=... POST_SCENE_ID=... envsubst < k8s/08-process-job.yaml | kubectl create -f -`

```bash
kubectl apply -f k8s/00-namespace.yaml -f k8s/01-configmap.yaml -f k8s/02-secret.yaml
kubectl apply -f k8s/03-postgres.yaml -f k8s/04-minio.yaml
kubectl apply -f k8s/05-migrate-job.yaml
kubectl wait --for=condition=complete job/migrate -n wildfirewatch --timeout=90s
kubectl apply -f k8s/06-api.yaml -f k8s/07-ingest-cronjob.yaml
```

Verified on a local cluster: every manifest applies and every pod reaches Ready, the ingest
CronJob's Job hit the live Earth Search STAC API and stored a real Sentinel-2 scene, and the
process Job template ran the full band-read/align/dNBR/vectorize pipeline to completion —
confirmed by querying the `api` Service from inside the cluster.

## AWS (Terraform)

`terraform/` provisions the production-hosted equivalent of the stack above: S3 (raw +
processed buckets, replacing MinIO), RDS PostgreSQL (replacing the `postgres` container — enable
PostGIS once with `CREATE EXTENSION postgis;` after the first apply, same as locally), EKS (runs
the same `k8s/` manifests), an ECR repository for the `api` image, and CloudWatch (EKS
control-plane log group, an app log group, an RDS free-storage alarm).

Written and validated (`terraform fmt`, `terraform validate`, and `terraform plan` — which gets
through building the full resource graph and only fails for lack of AWS credentials), but **not
applied** — review it, set a real `db_password`, and run it yourself:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # or set TF_VAR_db_password in the environment
terraform init
terraform plan
terraform apply
```

## Roadmap (not built in this pass)

- **EKS ingress/IRSA**: an ALB ingress controller for the `api` Service, and IRSA so pods use
  scoped IAM roles instead of the node role.
- **Shipping container logs to CloudWatch**: the `app` log group in `terraform/cloudwatch.tf`
  exists, but nothing yet ships the `api`/`wfw` containers' JSON stdout into it (e.g. the
  CloudWatch Container Insights EKS addon).
- **Grafana alerting**: the dashboard is read-only; no alert rules are wired to the failure/
  latency panels yet.
