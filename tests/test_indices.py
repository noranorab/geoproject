import numpy as np
from affine import Affine

from wildfirewatch.processing.burn_detection import classify_severity, vectorize_burn_areas
from wildfirewatch.processing.indices import dnbr, nbr, ndvi


def test_ndvi_known_values():
    nir = np.array([[0.8, 0.5]])
    red = np.array([[0.2, 0.5]])
    result = ndvi(nir, red)
    assert result[0, 0] == np.float32(0.6)
    assert result[0, 1] == np.float32(0.0)


def test_ndvi_handles_zero_denominator():
    nir = np.array([[0.0]])
    red = np.array([[0.0]])
    assert ndvi(nir, red)[0, 0] == 0.0


def test_nbr_known_values():
    nir = np.array([[0.9]])
    swir2 = np.array([[0.1]])
    result = nbr(nir, swir2)
    assert np.isclose(result[0, 0], 0.8)


def test_dnbr_is_pre_minus_post():
    pre = np.array([[0.5, 0.5]])
    post = np.array([[0.1, 0.6]])
    result = dnbr(pre, post)
    assert np.allclose(result, [[0.4, -0.1]])


def test_classify_severity_buckets():
    values = np.array([0.0, 0.05, 0.15, 0.3, 0.5])
    classified = classify_severity(values)
    assert list(classified) == [0, 0, 1, 2, 3]


def test_vectorize_burn_areas_detects_high_severity_patch():
    dnbr_arr = np.zeros((20, 20), dtype="float32")
    dnbr_arr[5:15, 5:15] = 0.6  # a 10x10 pixel high-severity patch

    # 10m pixels -> each pixel = 100 m^2 -> patch = 100 pixels = 1 ha
    transform = Affine(10, 0, 0, 0, -10, 0)

    polygons = vectorize_burn_areas(dnbr_arr, transform)

    assert len(polygons) == 1
    poly = polygons[0]
    assert poly.severity == "high"
    assert np.isclose(poly.dnbr_mean, 0.6, atol=1e-3)
    assert np.isclose(poly.area_ha, 1.0, rtol=0.05)


def test_vectorize_burn_areas_ignores_tiny_noise_patches():
    dnbr_arr = np.zeros((20, 20), dtype="float32")
    dnbr_arr[0, 0] = 0.5  # single stray pixel, below min_area_px default of 4

    transform = Affine(10, 0, 0, 0, -10, 0)
    polygons = vectorize_burn_areas(dnbr_arr, transform)

    assert polygons == []
