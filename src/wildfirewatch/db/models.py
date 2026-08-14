import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stac_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    satellite: Mapped[str] = mapped_column(String, default="sentinel-2")
    sensing_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cloud_cover: Mapped[float] = mapped_column(Float)
    bbox: Mapped[str] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326))
    bands: Mapped[dict] = mapped_column(JSONB, default=dict)
    s3_raw_prefix: Mapped[str] = mapped_column(String)
    processing_status: Mapped[str] = mapped_column(String, default="ingested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    detections: Mapped[list["Detection"]] = relationship(back_populates="scene")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenes.id"), index=True)
    geom: Mapped[str] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326))
    dnbr_mean: Mapped[float] = mapped_column(Float)
    area_ha: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scene: Mapped["Scene"] = relationship(back_populates="detections")
