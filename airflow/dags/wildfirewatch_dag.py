"""Per-AOI wildfire monitoring pipeline: ingest -> process -> notify.

Wraps the existing `wfw ingest` / `wfw process` CLI commands (unmodified) as Airflow
tasks. `select_scene_pair` and `notify_new_detections` are thin glue around the
wildfirewatch package's own DB session/models -- there is no pipeline logic here that
doesn't already live in `src/wildfirewatch`.

AOIs are read from the Airflow Variable `wfw_aois` (JSON list), falling back to the
Rhodes, Greece demo AOI from the project README so the DAG works out of the box.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, TaskGroup, Variable, task
from airflow.sdk.exceptions import AirflowSkipException

log = logging.getLogger(__name__)

DEFAULT_AOIS = [
    {
        "name": "rhodes-greece",
        "bbox": [27.9, 36.0, 28.2, 36.3],
        # Pre-fire baseline window -- matches the README quickstart demo. For a real
        # deployment this should be a fixed, known-clean reference window per AOI.
        "baseline_start": "2023-07-01",
        "baseline_end": "2023-07-20",
        "max_cloud_cover": 20,
        "lookback_days": 15,
    }
]


def _load_aois() -> list[dict]:
    return Variable.get("wfw_aois", default=DEFAULT_AOIS, deserialize_json=True)


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower())


@task
def select_scene_pair(aoi: dict) -> dict:
    """Pick the best pre-fire baseline scene and the newest not-yet-processed
    scene in the current monitoring window; skip the AOI if either is missing."""
    from geoalchemy2.shape import to_shape
    from shapely.geometry import box

    from wildfirewatch.db.models import Scene
    from wildfirewatch.db.session import SessionLocal

    aoi_box = box(*aoi["bbox"])
    baseline_start = datetime.fromisoformat(aoi["baseline_start"]).replace(tzinfo=UTC)
    baseline_end = datetime.fromisoformat(aoi["baseline_end"]).replace(tzinfo=UTC)

    session = SessionLocal()
    try:
        candidates = [s for s in session.query(Scene).all() if to_shape(s.bbox).intersects(aoi_box)]
    finally:
        session.close()

    baseline_candidates = [s for s in candidates if baseline_start <= s.sensing_time <= baseline_end]
    current_candidates = [
        s for s in candidates if s.sensing_time > baseline_end and s.processing_status != "processed"
    ]

    if not baseline_candidates:
        raise AirflowSkipException(f"No baseline scene ingested yet for {aoi['name']}")
    if not current_candidates:
        raise AirflowSkipException(f"No new scene to process yet for {aoi['name']}")

    pre = min(baseline_candidates, key=lambda s: s.cloud_cover)
    post = max(current_candidates, key=lambda s: s.sensing_time)
    return {"pre_scene_id": str(pre.id), "post_scene_id": str(post.id)}


@task
def notify_new_detections(aoi: dict, pair: dict) -> None:
    """Log (and optionally webhook-post) a summary if the run produced detections."""
    from wildfirewatch.db.models import Detection, Scene
    from wildfirewatch.db.session import SessionLocal

    session = SessionLocal()
    try:
        post_scene_id = pair["post_scene_id"]
        count = session.query(Detection).filter_by(scene_id=post_scene_id).count()
        scene = session.get(Scene, post_scene_id)
    finally:
        session.close()

    if count == 0:
        log.info("%s: scene %s processed, no burn-severity polygons detected", aoi["name"], post_scene_id)
        return

    message = (
        f"[WildfireWatch] {aoi['name']}: {count} burn-severity polygon(s) detected "
        f"in scene {post_scene_id} (sensed {scene.sensing_time.isoformat()})"
    )
    log.warning(message)

    webhook_url = Variable.get("wfw_notify_webhook_url", default=None)
    if webhook_url:
        import requests

        requests.post(webhook_url, json={"text": message}, timeout=10)


with DAG(
    dag_id="wildfirewatch_pipeline",
    description="Per-AOI ingest -> process -> notify wildfire monitoring pipeline",
    schedule="@weekly",
    start_date=datetime(2024, 1, 1, tzinfo=UTC),
    catchup=False,
    tags=["wildfirewatch"],
) as dag:
    for aoi in _load_aois():
        bbox_str = " ".join(str(v) for v in aoi["bbox"])
        max_cloud = aoi.get("max_cloud_cover", 20)
        lookback_days = aoi.get("lookback_days", 15)
        group_id = f"aoi_{_slug(aoi['name'])}"

        with TaskGroup(group_id=group_id):
            ingest_baseline = BashOperator(
                task_id="ingest_baseline",
                bash_command=(
                    f"wfw ingest --bbox {bbox_str} "
                    f"--start {aoi['baseline_start']} --end {aoi['baseline_end']} "
                    f"--max-cloud-cover {max_cloud} --limit 3"
                ),
            )

            ingest_current = BashOperator(
                task_id="ingest_current",
                bash_command=(
                    f"wfw ingest --bbox {bbox_str} "
                    "--start {{ (data_interval_end - macros.timedelta(days="
                    + str(lookback_days)
                    + ")).strftime('%Y-%m-%d') }} "
                    "--end {{ data_interval_end.strftime('%Y-%m-%d') }} "
                    f"--max-cloud-cover {max_cloud} --limit 5"
                ),
            )

            pair = select_scene_pair(aoi)

            select_task_path = f"{group_id}.select_scene_pair"
            process_pair = BashOperator(
                task_id="process_pair",
                bash_command=(
                    "wfw process --pre-scene-id "
                    "{{ ti.xcom_pull(task_ids='" + select_task_path + "')['pre_scene_id'] }} "
                    "--post-scene-id "
                    "{{ ti.xcom_pull(task_ids='" + select_task_path + "')['post_scene_id'] }}"
                ),
            )

            notify = notify_new_detections(aoi, pair)

            [ingest_baseline, ingest_current] >> pair >> process_pair >> notify
