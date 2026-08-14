"""initial schema

Revision ID: 7fc476240a7f
Revises:
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7fc476240a7f"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "scenes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("stac_id", sa.String(), nullable=False),
        sa.Column("satellite", sa.String(), nullable=False, server_default="sentinel-2"),
        sa.Column("sensing_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cloud_cover", sa.Float(), nullable=False),
        sa.Column(
            "bbox",
            geoalchemy2.Geometry(geometry_type="POLYGON", srid=4326),
            nullable=False,
        ),
        sa.Column("bands", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("s3_raw_prefix", sa.String(), nullable=False),
        sa.Column("processing_status", sa.String(), nullable=False, server_default="ingested"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_scenes_stac_id", "scenes", ["stac_id"], unique=True)
    op.create_index("ix_scenes_bbox", "scenes", ["bbox"], unique=False, postgresql_using="gist")

    op.create_table(
        "detections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scene_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scenes.id"),
            nullable=False,
        ),
        sa.Column(
            "geom",
            geoalchemy2.Geometry(geometry_type="POLYGON", srid=4326),
            nullable=False,
        ),
        sa.Column("dnbr_mean", sa.Float(), nullable=False),
        sa.Column("area_ha", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_detections_scene_id", "detections", ["scene_id"])
    op.create_index("ix_detections_geom", "detections", ["geom"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_table("detections")
    op.drop_table("scenes")
