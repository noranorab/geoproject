from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

from wildfirewatch.api.schemas import (
    DetectionFeature,
    DetectionFeatureCollection,
    DetectionProperties,
)
from wildfirewatch.db.models import Detection
from wildfirewatch.db.session import get_session

router = APIRouter(prefix="/detections", tags=["detections"])

_SEVERITY_ORDER = {"low": 1, "moderate": 2, "high": 3}


def _to_feature(d: Detection) -> DetectionFeature:
    return DetectionFeature(
        geometry=mapping(to_shape(d.geom)),
        properties=DetectionProperties(
            id=d.id,
            scene_id=d.scene_id,
            severity=d.severity,
            dnbr_mean=d.dnbr_mean,
            area_ha=d.area_ha,
            confidence=d.confidence,
            detected_at=d.detected_at,
        ),
    )


@router.get("", response_model=DetectionFeatureCollection)
def list_detections(
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    min_severity: str | None = Query(None, description="low|moderate|high"),
    session: Session = Depends(get_session),
):
    stmt = select(Detection)
    if start is not None:
        stmt = stmt.where(Detection.detected_at >= start)
    if end is not None:
        stmt = stmt.where(Detection.detected_at <= end)
    if min_severity is not None:
        threshold = _SEVERITY_ORDER.get(min_severity, 1)
        allowed = [k for k, v in _SEVERITY_ORDER.items() if v >= threshold]
        stmt = stmt.where(Detection.severity.in_(allowed))

    detections = session.execute(stmt.order_by(Detection.detected_at.desc())).scalars().all()
    return DetectionFeatureCollection(features=[_to_feature(d) for d in detections])


@router.get("/{detection_id}", response_model=DetectionFeature)
def get_detection(detection_id: str, session: Session = Depends(get_session)):
    detection = session.get(Detection, detection_id)
    if detection is None:
        raise HTTPException(status_code=404, detail="detection not found")
    return _to_feature(detection)
