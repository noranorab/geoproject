import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stac_id: str
    satellite: str
    sensing_time: datetime
    cloud_cover: float
    bbox: dict[str, Any]
    bands: dict[str, Any]
    processing_status: str


class DetectionProperties(BaseModel):
    id: uuid.UUID
    scene_id: uuid.UUID
    severity: str
    dnbr_mean: float
    area_ha: float
    confidence: float
    detected_at: datetime


class DetectionFeature(BaseModel):
    type: str = "Feature"
    geometry: dict[str, Any]
    properties: DetectionProperties


class DetectionFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[DetectionFeature]
