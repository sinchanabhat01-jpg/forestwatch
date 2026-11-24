import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np
from app import analysis as an

TH = dict(ndvi_forest_min=0.6, ndvi_loss_max=0.35, ndvi_drop_min=0.25, ndvi_uncertain_drop=0.15, nbr_burn_drop=0.27, burn_max_nir=0.18, min_patch_pixels=8)
BBOX = [-60.0, -3.0, -59.9, -2.9]  # ~11 km x 11 km


def test_synthetic_pair():
    b, a = an.synthetic_pair()
    st, cls = an.detect(b, a, BBOX, TH)
    assert st["loss_ha"] > 0 and st["uncertain_ha"] > 0
    assert (cls == 3).sum() > 0
    assert st["fire_ha"] > 0 and st["loss_ha"] > st["fire_ha"] * 0.5
    assert (cls[:80, 330:] != 3).all(), "cloud corner must never be classed as loss"
    assert 0 < st["loss_pct_of_forest"] < 25
    assert st["mean_ndvi_before"] > st["mean_ndvi_after"]
    assert an.overlay_png(cls)[:4] == b"\x89PNG"


def test_no_change_gives_no_loss():
    b, _ = an.synthetic_pair()
    st, cls = an.detect(b, b.copy(), BBOX, TH)
    assert st["loss_ha"] == 0 and st["uncertain_ha"] == 0


def test_area_math():
    ha = an.pixel_area_ha([0, 0, 0.1, 0.1], (100, 100))
    assert abs(ha * 10000 - (11132 * 11057) / 10000) < 5


def test_severity():
    s = dict(medium=10, high=50, critical=200)
    assert [an.severity(x, s) for x in (1, 10, 50, 200)] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


if __name__ == "__main__":
    for f in (test_synthetic_pair, test_no_change_gives_no_loss, test_area_math, test_severity):
        f(); print("PASS", f.__name__)
