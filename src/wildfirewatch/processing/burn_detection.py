from dataclasses import dataclass

import numpy as np
from affine import Affine
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape

# Simplified USGS dNBR severity thresholds (unscaled ratio, not the x1000 legacy DN scale).
SEVERITY_THRESHOLDS = (
    (0.10, "low"),
    (0.27, "moderate"),
    (0.44, "high"),
)


@dataclass
class BurnPolygon:
    geometry: object  # shapely geometry, in the raster's native CRS
    severity: str
    dnbr_mean: float
    area_ha: float


def classify_severity(dnbr: np.ndarray) -> np.ndarray:
    """Bucket a dNBR array into 0=unburned,1=low,2=moderate,3=high."""
    classified = np.zeros(dnbr.shape, dtype="uint8")
    classified[(dnbr > SEVERITY_THRESHOLDS[0][0]) & (dnbr <= SEVERITY_THRESHOLDS[1][0])] = 1
    classified[(dnbr > SEVERITY_THRESHOLDS[1][0]) & (dnbr <= SEVERITY_THRESHOLDS[2][0])] = 2
    classified[dnbr > SEVERITY_THRESHOLDS[2][0]] = 3
    return classified


_LABELS = {1: "low", 2: "moderate", 3: "high"}


def vectorize_burn_areas(
    dnbr: np.ndarray, transform: Affine, min_area_px: int = 4
) -> list[BurnPolygon]:
    """Classify + vectorize a dNBR raster into burn-severity polygons (raster's native CRS)."""
    classified = classify_severity(dnbr)
    results: list[BurnPolygon] = []

    # Per-class connected-component labeling + vectorized ndimage.mean, not a
    # rasterize() per polygon — scenes can produce thousands of small noisy patches.
    for value, severity in _LABELS.items():
        class_mask = classified == value
        if not class_mask.any():
            continue

        labeled, num_labels = ndimage.label(class_mask)
        if num_labels == 0:
            continue

        label_ids = np.arange(1, num_labels + 1)
        mean_dnbr_by_label = ndimage.mean(dnbr, labels=labeled, index=label_ids)
        pixel_count_by_label = ndimage.sum(class_mask, labels=labeled, index=label_ids)

        for geom, label_value in shapes(labeled, mask=class_mask, transform=transform):
            label_id = int(label_value)
            if pixel_count_by_label[label_id - 1] < min_area_px:
                continue

            polygon = shape(geom)
            area_m2 = polygon.area  # valid because transform/crs are in a projected (metric) CRS

            results.append(
                BurnPolygon(
                    geometry=polygon,
                    severity=severity,
                    dnbr_mean=float(mean_dnbr_by_label[label_id - 1]),
                    area_ha=area_m2 / 10_000,
                )
            )

    return results
