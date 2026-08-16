import tempfile
import time
import uuid
from pathlib import Path

import click
import numpy as np
import rasterio
from affine import Affine
from geoalchemy2.shape import from_shape
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.warp import Resampling, reproject
from shapely.ops import transform as shapely_transform

from wildfirewatch.config import get_settings
from wildfirewatch.db.models import Detection, Scene
from wildfirewatch.db.session import SessionLocal
from wildfirewatch.observability import (
    configure_logging,
    detections_stored_total,
    get_logger,
    processing_duration_seconds,
    processing_jobs_total,
    push_metrics,
)
from wildfirewatch.processing.burn_detection import vectorize_burn_areas
from wildfirewatch.processing.indices import dnbr as compute_dnbr
from wildfirewatch.processing.indices import nbr as compute_nbr
from wildfirewatch.processing.indices import ndvi as compute_ndvi
from wildfirewatch.storage.s3 import download_file, upload_file

log = get_logger(__name__)


def _read_band(scene: Scene, band: str, bucket: str, tmp: Path):
    local_path = tmp / f"{scene.id}_{band}.tif"
    download_file(bucket, scene.bands[band], local_path)
    with rasterio.open(local_path) as src:
        return src.read(1), src.transform, src.crs


def _align_to(
    array: np.ndarray,
    src_transform: Affine,
    src_crs: CRS,
    dst_transform: Affine,
    dst_crs: CRS,
    dst_shape: tuple[int, int],
    resampling: Resampling = Resampling.bilinear,
) -> np.ndarray:
    """Resample a band onto another band's exact pixel grid (also needed within a single
    scene: Sentinel-2's SWIR2 is native 20m while NIR/red are native 10m)."""
    # Categorical bands (e.g. SCL) need nearest-neighbor — bilinear would blend
    # classification codes into meaningless values.
    dtype = "float32" if resampling != Resampling.nearest else array.dtype
    dst = np.empty(dst_shape, dtype=dtype)
    reproject(
        source=array.astype(dtype),
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=resampling,
    )
    return dst


# Sentinel-2 SCL codes to exclude: 0 no-data, 1 saturated, 3 cloud shadow, 6 water,
# 8/9 cloud, 10 cirrus, 11 snow. 5 (bare soil) is kept — burn scars reclassify as this.
_SCL_INVALID_CLASSES = {0, 1, 3, 6, 8, 9, 10, 11}


def _valid_mask(scl: np.ndarray) -> np.ndarray:
    return ~np.isin(scl.astype("uint8"), list(_SCL_INVALID_CLASSES))


@click.command()
@click.option("--pre-scene-id", required=True, type=click.UUID, help="Baseline (pre-fire) scene")
@click.option("--post-scene-id", required=True, type=click.UUID, help="Post-fire scene to detect burns in")
def process(pre_scene_id, post_scene_id):
    """Compute NDVI/NBR/dNBR for a pre/post scene pair and store burn-area detections."""
    configure_logging()
    settings = get_settings()
    session = SessionLocal()
    started = time.perf_counter()
    try:
        pre_scene = session.get(Scene, pre_scene_id)
        post_scene = session.get(Scene, post_scene_id)
        if pre_scene is None or post_scene is None:
            raise click.ClickException("pre/post scene id not found in the database")

        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            bucket = settings.s3_raw_bucket

            # NIR (10m) is the reference grid everything else resamples onto.
            log.info("reading_bands", pre_scene_id=str(pre_scene_id), post_scene_id=str(post_scene_id))
            post_nir, post_transform, post_crs = _read_band(post_scene, "nir", bucket, tmp)
            post_shape = post_nir.shape
            log.info("grid_resolved", width=post_shape[1], height=post_shape[0])

            post_swir2_raw, post_swir2_t, post_swir2_crs = _read_band(post_scene, "swir22", bucket, tmp)
            post_swir2 = _align_to(post_swir2_raw, post_swir2_t, post_swir2_crs, post_transform, post_crs, post_shape)

            post_red_raw, post_red_t, post_red_crs = _read_band(post_scene, "red", bucket, tmp)
            post_red = _align_to(post_red_raw, post_red_t, post_red_crs, post_transform, post_crs, post_shape)

            pre_nir_raw, pre_nir_t, pre_nir_crs = _read_band(pre_scene, "nir", bucket, tmp)
            pre_nir = _align_to(pre_nir_raw, pre_nir_t, pre_nir_crs, post_transform, post_crs, post_shape)

            pre_swir2_raw, pre_swir2_t, pre_swir2_crs = _read_band(pre_scene, "swir22", bucket, tmp)
            pre_swir2 = _align_to(pre_swir2_raw, pre_swir2_t, pre_swir2_crs, post_transform, post_crs, post_shape)

            # Cloud/shadow/water/snow pixels invalid in *either* date get excluded —
            # open sea alone can otherwise outsize the real fire scar in the output.
            post_scl_raw, post_scl_t, post_scl_crs = _read_band(post_scene, "scl", bucket, tmp)
            post_scl = _align_to(
                post_scl_raw, post_scl_t, post_scl_crs, post_transform, post_crs, post_shape, Resampling.nearest
            )
            pre_scl_raw, pre_scl_t, pre_scl_crs = _read_band(pre_scene, "scl", bucket, tmp)
            pre_scl = _align_to(
                pre_scl_raw, pre_scl_t, pre_scl_crs, post_transform, post_crs, post_shape, Resampling.nearest
            )
            valid_mask = _valid_mask(post_scl) & _valid_mask(pre_scl)
            log.info("valid_mask_computed", valid_pct=round(valid_mask.mean() * 100, 1))

            pre_nbr = compute_nbr(pre_nir, pre_swir2)
            post_nbr = compute_nbr(post_nir, post_swir2)
            dnbr = compute_dnbr(pre_nbr, post_nbr)
            dnbr = np.where(valid_mask, dnbr, 0.0)
            post_ndvi = compute_ndvi(post_nir, post_red)

            log.info("vectorizing_burn_areas")
            burn_polygons = vectorize_burn_areas(dnbr, post_transform, min_area_px=25)
            log.info("burn_polygons_found", count=len(burn_polygons))

            transformer = Transformer.from_crs(post_crs, "EPSG:4326", always_xy=True)

            for poly in burn_polygons:
                geom_4326 = shapely_transform(transformer.transform, poly.geometry)
                detection = Detection(
                    id=uuid.uuid4(),
                    scene_id=post_scene.id,
                    geom=from_shape(geom_4326, srid=4326),
                    dnbr_mean=poly.dnbr_mean,
                    area_ha=poly.area_ha,
                    severity=poly.severity,
                    detected_at=post_scene.sensing_time,
                )
                session.add(detection)

            profile_path = tmp / f"{post_scene.id}_nir.tif"
            with rasterio.open(profile_path) as ref:
                profile = ref.profile.copy()
            profile.update(dtype="float32", count=1)

            ndvi_path = tmp / "ndvi.tif"
            with rasterio.open(ndvi_path, "w", **profile) as dst:
                dst.write(post_ndvi.astype("float32"), 1)
            upload_file(ndvi_path, settings.s3_processed_bucket, f"{post_scene.id}/ndvi.tif")

            dnbr_path = tmp / "dnbr.tif"
            with rasterio.open(dnbr_path, "w", **profile) as dst:
                dst.write(dnbr.astype("float32"), 1)
            upload_file(dnbr_path, settings.s3_processed_bucket, f"{post_scene.id}/dnbr.tif")

            post_scene.processing_status = "processed"
            session.commit()
            detections_stored_total.inc(len(burn_polygons))
            processing_jobs_total.labels(status="success").inc()
            log.info("processing_complete", scene_id=str(post_scene.id), detections=len(burn_polygons))
    except Exception:
        processing_jobs_total.labels(status="failed").inc()
        raise
    finally:
        processing_duration_seconds.observe(time.perf_counter() - started)
        session.close()
        push_metrics("wfw_process")
