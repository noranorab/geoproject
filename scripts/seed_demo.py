"""One-time demo-data seed for hosted read-only previews (e.g. Render), where
running the real STAC ingest + raster processing pipeline at deploy time
isn't practical (no object storage, no time budget for a multi-minute build).

Loads demo/rhodes_2023_fixture.json -- the actual output of `wfw ingest` +
`wfw process` against the real pre/post Rhodes, Greece 2023 wildfire scenes
(see README Quickstart), not synthetic data. Idempotent: does nothing if the
scenes table isn't empty, so redeploys don't duplicate rows.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from geoalchemy2.shape import from_shape
from shapely.geometry import shape

from wildfirewatch.db.models import Detection, Scene
from wildfirewatch.db.session import SessionLocal

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "demo" / "rhodes_2023_fixture.json"


def main() -> None:
    session = SessionLocal()
    try:
        if session.query(Scene).count() > 0:
            print("Demo data already present, skipping seed.")
            return

        data = json.loads(FIXTURE_PATH.read_text())

        for s in data["scenes"]:
            session.add(
                Scene(
                    id=uuid.UUID(s["id"]),
                    stac_id=s["stac_id"],
                    satellite=s["satellite"],
                    sensing_time=datetime.fromisoformat(s["sensing_time"]),
                    cloud_cover=s["cloud_cover"],
                    bbox=from_shape(shape(s["bbox"]), srid=4326),
                    bands=s["bands"],
                    s3_raw_prefix=s["s3_raw_prefix"],
                    processing_status=s["processing_status"],
                )
            )
        for d in data["detections"]:
            session.add(
                Detection(
                    id=uuid.UUID(d["id"]),
                    scene_id=uuid.UUID(d["scene_id"]),
                    geom=from_shape(shape(d["geom"]), srid=4326),
                    dnbr_mean=d["dnbr_mean"],
                    area_ha=d["area_ha"],
                    severity=d["severity"],
                    confidence=d["confidence"],
                    detected_at=datetime.fromisoformat(d["detected_at"]),
                )
            )
        session.commit()
        print(f"Seeded {len(data['scenes'])} scenes, {len(data['detections'])} detections")
    finally:
        session.close()


if __name__ == "__main__":
    main()
