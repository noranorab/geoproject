import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import box
from sqlalchemy.orm import Session

from wildfirewatch.api.main import app
from wildfirewatch.db.models import Detection, Scene
from wildfirewatch.db.session import get_engine, get_session

# Integration tests: exercise the real PostGIS backend (geometry columns aren't
# supported by SQLite), so `docker compose up -d postgres` + `alembic upgrade head`
# must have already been run. Tables are managed by Alembic, not by these tests —
# each test only cleans up the rows it inserted, so this suite never touches schema
# that real pipeline runs depend on.


@pytest.fixture()
def db_session():
    engine = get_engine()
    session = Session(bind=engine)
    yield session
    session.query(Detection).delete()
    session.query(Scene).delete()
    session.commit()
    session.close()


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def scene(db_session):
    s = Scene(
        stac_id=f"test-{uuid.uuid4()}",
        satellite="sentinel-2",
        sensing_time=datetime(2023, 7, 24, tzinfo=UTC),
        cloud_cover=5.0,
        bbox=from_shape(box(27.9, 36.0, 28.2, 36.3), srid=4326),
        bands={"nir": "x/nir.tif"},
        s3_raw_prefix="s3://raw/test",
        processing_status="processed",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


def test_health():
    with TestClient(app) as c:
        resp = c.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_list_scenes_returns_created_scene(client, scene):
    resp = client.get("/scenes")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert str(scene.id) in ids


def test_get_scene_by_id(client, scene):
    resp = client.get(f"/scenes/{scene.id}")
    assert resp.status_code == 200
    assert resp.json()["stac_id"] == scene.stac_id


def test_get_scene_404(client):
    resp = client.get(f"/scenes/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_list_detections_returns_geojson(client, db_session, scene):
    d = Detection(
        id=uuid.uuid4(),
        scene_id=scene.id,
        geom=from_shape(box(28.0, 36.1, 28.05, 36.15), srid=4326),
        dnbr_mean=0.5,
        area_ha=12.3,
        severity="high",
        detected_at=datetime(2023, 7, 25, tzinfo=UTC),
    )
    db_session.add(d)
    db_session.commit()

    resp = client.get("/detections")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert any(f["properties"]["id"] == str(d.id) for f in body["features"])


def test_list_detections_min_severity_filter(client, db_session, scene):
    low = Detection(
        id=uuid.uuid4(),
        scene_id=scene.id,
        geom=from_shape(box(28.0, 36.1, 28.01, 36.11), srid=4326),
        dnbr_mean=0.15,
        area_ha=1.0,
        severity="low",
        detected_at=datetime(2023, 7, 25, tzinfo=UTC),
    )
    db_session.add(low)
    db_session.commit()

    resp = client.get("/detections", params={"min_severity": "high"})
    assert resp.status_code == 200
    severities = {f["properties"]["severity"] for f in resp.json()["features"]}
    assert "low" not in severities


def test_get_detection_404(client):
    resp = client.get(f"/detections/{uuid.uuid4()}")
    assert resp.status_code == 404
