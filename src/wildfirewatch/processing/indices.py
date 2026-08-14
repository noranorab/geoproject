import numpy as np


def _safe_ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a.astype("float32")
    b = b.astype("float32")
    denom = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(denom == 0, 0.0, (a - b) / denom)


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index: vegetation health/density."""
    return _safe_ratio(nir, red)


def nbr(nir: np.ndarray, swir2: np.ndarray) -> np.ndarray:
    """Normalized Burn Ratio: healthy vegetation vs. burned/bare ground."""
    return _safe_ratio(nir, swir2)


def dnbr(pre_nbr: np.ndarray, post_nbr: np.ndarray) -> np.ndarray:
    """Delta NBR: positive values indicate vegetation/burn severity increase."""
    return pre_nbr - post_nbr
