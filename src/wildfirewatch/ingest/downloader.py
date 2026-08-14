from pathlib import Path

import rasterio
from pystac import Item
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from wildfirewatch.storage.s3 import upload_file

# Bands needed downstream: red/nir for NDVI, nir/swir22 for NBR, scl for cloud/quality masking.
BANDS = ["red", "nir", "swir22", "scl"]


def _vsicurl(url: str) -> str:
    return f"/vsicurl/{url}"


def download_bands_for_aoi(
    item: Item, bbox_4326: tuple[float, float, float, float], out_dir: Path
) -> dict[str, Path]:
    """Window-read each required band, cropped to the AOI, without downloading the full scene."""
    out_dir.mkdir(parents=True, exist_ok=True)
    local_paths: dict[str, Path] = {}

    for band in BANDS:
        asset = item.assets[band]
        with rasterio.open(_vsicurl(asset.href)) as src:
            left, bottom, right, top = transform_bounds("EPSG:4326", src.crs, *bbox_4326)
            window = from_bounds(left, bottom, right, top, transform=src.transform)
            window = window.round_offsets().round_lengths()
            data = src.read(1, window=window)
            transform = src.window_transform(window)
            profile = src.profile.copy()
            profile.update(height=data.shape[0], width=data.shape[1], transform=transform, count=1)

        out_path = out_dir / f"{band}.tif"
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data, 1)
        local_paths[band] = out_path

    return local_paths


def upload_bands(local_paths: dict[str, Path], bucket: str, scene_prefix: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for band, path in local_paths.items():
        key = f"{scene_prefix}/{band}.tif"
        upload_file(path, bucket, key)
        keys[band] = key
    return keys
