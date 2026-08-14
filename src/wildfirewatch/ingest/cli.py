import tempfile
from pathlib import Path

import click
from geoalchemy2.shape import from_shape
from shapely.geometry import box

from wildfirewatch.config import get_settings
from wildfirewatch.db.models import Scene
from wildfirewatch.db.session import SessionLocal
from wildfirewatch.ingest.downloader import download_bands_for_aoi, upload_bands
from wildfirewatch.ingest.stac_client import search_scenes


@click.command()
@click.option(
    "--bbox",
    nargs=4,
    type=float,
    required=True,
    metavar="MIN_LON MIN_LAT MAX_LON MAX_LAT",
)
@click.option("--start", "start_date", required=True, help="YYYY-MM-DD")
@click.option("--end", "end_date", required=True, help="YYYY-MM-DD")
@click.option("--max-cloud-cover", default=20.0, show_default=True)
@click.option("--limit", default=5, show_default=True, help="Max scenes to ingest")
def ingest(bbox, start_date, end_date, max_cloud_cover, limit):
    """Search Earth Search STAC and ingest matching Sentinel-2 scenes into MinIO + PostGIS."""
    settings = get_settings()
    items = search_scenes(bbox, start_date, end_date, max_cloud_cover, limit)
    if not items:
        click.echo("No scenes found for the given filters.")
        return

    session = SessionLocal()
    try:
        for item in items:
            existing = session.query(Scene).filter_by(stac_id=item.id).one_or_none()
            if existing:
                click.echo(f"Skipping {item.id} (already ingested as {existing.id})")
                continue

            cloud = item.properties.get("eo:cloud_cover", 0.0)
            click.echo(f"Ingesting {item.id} (cloud cover {cloud:.1f}%)")

            with tempfile.TemporaryDirectory() as tmp:
                local_paths = download_bands_for_aoi(item, bbox, Path(tmp))
                band_keys = upload_bands(local_paths, settings.s3_raw_bucket, item.id)

            scene = Scene(
                stac_id=item.id,
                satellite="sentinel-2",
                sensing_time=item.datetime,
                cloud_cover=cloud,
                bbox=from_shape(box(*bbox), srid=4326),
                bands=band_keys,
                s3_raw_prefix=f"s3://{settings.s3_raw_bucket}/{item.id}",
                processing_status="ingested",
            )
            session.add(scene)
            session.commit()
            click.echo(f"  -> stored scene {scene.id}")
    finally:
        session.close()
