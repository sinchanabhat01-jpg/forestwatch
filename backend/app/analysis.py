"""Transparent NDVI / NBR change-detection pipeline (no trained ML model).

Input per date: float array (H, W, 7) with bands [B02, B03, B04, B08, B12, SCL, dataMask].
Reflectance is 0..1. SCL is the Sentinel-2 L2A scene classification.
"""
import io
import math
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

B02, B03, B04, B08, B12, SCL, MASK = range(7)
# SCL classes treated as unusable: no data, saturated, cloud shadow, cloud medium/high, cirrus, snow/ice
BAD_SCL = (0, 1, 3, 8, 9, 10, 11)
WATER_SCL = 6


def ndvi(a):
    nir, red = a[..., B08], a[..., B04]
    return (nir - red) / np.maximum(nir + red, 1e-6)


def nbr(a):
    nir, swir = a[..., B08], a[..., B12]
    return (nir - swir) / np.maximum(nir + swir, 1e-6)


def valid_mask(a):
    return (a[..., MASK] > 0) & ~np.isin(a[..., SCL].astype(np.int32), BAD_SCL)


def pixel_area_ha(bbox, shape):
    w, s, e, n = bbox
    lat = (s + n) / 2
    width_m = (e - w) * 111_320 * math.cos(math.radians(lat))
    height_m = (n - s) * 110_574
    return (width_m / shape[1]) * (height_m / shape[0]) / 10_000


def bbox_area_ha(bbox):
    w, s, e, n = bbox
    lat = (s + n) / 2
    return (e - w) * 111_320 * math.cos(math.radians(lat)) * (n - s) * 110_574 / 10_000


def _clean(mask, min_px):
    if min_px <= 1 or not mask.any():
        return mask
    lab, n = ndi.label(mask)
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= min_px
    return keep[lab]


def detect(before, after, bbox, th):
    """Return (stats dict, class_map uint8). Classes: 0 nodata, 1 non-forest, 2 stable forest,
    3 suspected loss, 4 uncertain (seasonal/partial), 5 probable fire."""
    nb, na = ndvi(before), ndvi(after)
    valid = valid_mask(before) & valid_mask(after)
    d = na - nb
    dnbr = nbr(before) - nbr(after)

    forest_before = valid & (nb >= th["ndvi_forest_min"])
    water_after = after[..., SCL].astype(np.int32) == WATER_SCL
    # dNBR alone cannot separate fire from clearing (bare soil also loses NBR). Burn scars are
    # dark in the NIR after the event, cleared soil/pasture stays bright, so require both.
    burn = (forest_before & (dnbr >= th["nbr_burn_drop"]) & (d <= -th["ndvi_uncertain_drop"])
            & (after[..., B08] <= th["burn_max_nir"]))
    loss = forest_before & ~burn & ~water_after & (na <= th["ndvi_loss_max"]) & (d <= -th["ndvi_drop_min"])
    loss = _clean(loss, th["min_patch_pixels"])
    uncertain = forest_before & ~burn & ~loss & ~water_after & (d <= -th["ndvi_uncertain_drop"])
    stable = forest_before & ~loss & ~uncertain & ~burn

    cls = np.zeros(nb.shape, np.uint8)
    cls[valid] = 1
    cls[stable] = 2
    cls[uncertain] = 4
    cls[burn] = 5
    cls[loss] = 3

    ha = pixel_area_ha(bbox, nb.shape)
    forest_ha = float(forest_before.sum() * ha)
    loss_ha = float(loss.sum() * ha)
    vf = float(valid.mean()) if valid.size else 0.0
    mean_b = float(nb[valid].mean()) if valid.any() else None
    mean_a = float(na[valid].mean()) if valid.any() else None
    fmean_b = float(nb[forest_before].mean()) if forest_before.any() else None
    fmean_a = float(na[forest_before].mean()) if forest_before.any() else None
    stats = {
        "mean_ndvi_before": mean_b, "mean_ndvi_after": mean_a,
        "forest_mean_ndvi_before": fmean_b, "forest_mean_ndvi_after": fmean_a,
        "forest_area_ha": forest_ha, "loss_ha": loss_ha,
        "uncertain_ha": float(uncertain.sum() * ha), "fire_ha": float(burn.sum() * ha),
        "loss_pct_of_forest": (100 * loss_ha / forest_ha) if forest_ha > 0 else 0.0,
        "valid_pixel_pct": 100 * vf, "pixel_area_ha": ha,
        "total_area_ha": bbox_area_ha(bbox),
    }
    return stats, cls


def true_color_png(a, gain=3.0):
    rgb = np.clip(a[..., [B04, B03, B02]] * gain, 0, 1) ** (1 / 1.2)
    return _png((rgb * 255).astype(np.uint8))


def ndvi_png(a):
    v = np.clip(ndvi(a), -0.2, 0.9)
    t = (v + 0.2) / 1.1
    rgb = np.stack([(1 - t) * 190 + t * 20, 60 + t * 170, 40 + (1 - t) * 20], -1)
    rgb[~valid_mask(a)] = (40, 40, 40)
    return _png(rgb.astype(np.uint8))


def false_color_png(a, gain=2.5):
    rgb = np.clip(a[..., [B08, B04, B03]] * gain, 0, 1) ** (1 / 1.2)
    return _png((rgb * 255).astype(np.uint8))


COLORS = {2: (34, 197, 94, 110), 3: (239, 68, 68, 200), 4: (250, 204, 21, 160), 5: (249, 115, 22, 170)}


def overlay_png(cls):
    rgba = np.zeros(cls.shape + (4,), np.uint8)
    for k, c in COLORS.items():
        rgba[cls == k] = c
    return _png(rgba)


def _png(arr):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def severity(loss_ha, s):
    if loss_ha >= s["critical"]: return "CRITICAL"
    if loss_ha >= s["high"]: return "HIGH"
    if loss_ha >= s["medium"]: return "MEDIUM"
    return "LOW"


def write_report(st, before_date, after_date, place, is_demo, th):
    lines = []
    if is_demo:
        lines.append("DEMO DATA: this scene is synthetic and does not depict a real place.")
    lines.append(f"Area analysed: {place or 'selected area'} ({st['total_area_ha']:.0f} ha). "
                 f"Images compared: {before_date} (older) and {after_date} (recent).")
    lines.append(f"Usable pixels (cloud, shadow and no-data excluded): {st['valid_pixel_pct']:.1f}%.")
    if st["valid_pixel_pct"] < 60:
        lines.append("Warning: less than 60% of the area was usable in both images, so results are incomplete. Try other dates or a lower cloud limit.")
    if st["forest_area_ha"] <= 0:
        lines.append(f"No pixels reached the forest NDVI threshold ({th['ndvi_forest_min']}) in the older image, so no forest loss can be assessed here.")
    else:
        lines.append(f"Forest-like vegetation (NDVI >= {th['ndvi_forest_min']}) covered about {st['forest_area_ha']:.1f} ha in the older image.")
        lines.append(f"Suspected forest loss: {st['loss_ha']:.1f} ha ({st['loss_pct_of_forest']:.2f}% of that forest). "
                     f"A pixel counts as loss when NDVI falls by at least {th['ndvi_drop_min']} and ends at or below {th['ndvi_loss_max']}.")
        if st["uncertain_ha"] > 0:
            lines.append(f"Uncertain change: {st['uncertain_ha']:.1f} ha lost some greenness but not enough to confirm clearing. Seasonal leaf drop, drought or thinning are possible; compare same-season dates.")
        if st["fire_ha"] > 0:
            lines.append(f"Probable fire scar: {st['fire_ha']:.1f} ha shows a burn signature (dNBR >= {th['nbr_burn_drop']} and dark NIR <= {th['burn_max_nir']}) and is kept separate from clearing.")
    lines.append("Method: rule-based NDVI/NBR change detection on Sentinel-2 L2A. No trained model was used, so no model confidence is reported. Validate hotspots against high-resolution imagery or field data before acting.")
    return "\n".join(lines)


# ---- synthetic scene, used only for clearly labelled demo mode and tests ----
def synthetic_pair(size=400, seed=7):
    rng = np.random.default_rng(seed)
    def scene(forest_mask, noise):
        a = np.zeros((size, size, 7), np.float32)
        veg = forest_mask
        red = np.where(veg, 0.03, 0.18) + rng.normal(0, noise, (size, size))
        nir = np.where(veg, 0.42, 0.24) + rng.normal(0, noise, (size, size))
        a[..., B04], a[..., B08] = np.clip(red, 0.005, 1), np.clip(nir, 0.005, 1)
        a[..., B03] = np.where(veg, 0.06, 0.16)
        a[..., B02] = np.where(veg, 0.03, 0.13)
        a[..., B12] = np.where(veg, 0.12, 0.30)
        a[..., SCL] = 4
        a[..., MASK] = 1
        return a
    yy, xx = np.mgrid[:size, :size]
    forest = ((xx - size / 2) ** 2 + (yy - size / 2) ** 2) < (size * 0.45) ** 2
    cleared = forest & (((xx - 0.62 * size) ** 2 + (yy - 0.4 * size) ** 2) < (size * 0.12) ** 2)
    cleared |= forest & (xx > 0.3 * size) & (xx < 0.45 * size) & (yy > 0.65 * size) & (yy < 0.78 * size)
    thinned = forest & ~cleared & (((xx - 0.35 * size) ** 2 + (yy - 0.3 * size) ** 2) < (size * 0.08) ** 2)
    before, after = scene(forest, 0.008), scene(forest & ~cleared, 0.008)
    after[thinned, B08] -= 0.12
    cloud = (xx > 0.8 * size) & (yy < 0.2 * size)
    after[cloud, SCL] = 9
    burned = forest & ~cleared & ~thinned & (((xx - 0.3 * size) ** 2 + (yy - 0.55 * size) ** 2) < (size * 0.07) ** 2)
    after[burned, B04], after[burned, B08], after[burned, B12] = 0.07, 0.10, 0.18
    return before, after
