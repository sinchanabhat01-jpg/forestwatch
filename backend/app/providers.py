"""All outbound calls to external services. API secrets never leave the backend."""
import io
import time
import threading
from datetime import date, timedelta
import httpx
import numpy as np
import tifffile
from .config import settings

TIMEOUT = httpx.Timeout(60.0, connect=10.0)
CDSE_ODATA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
GFW_API = "https://data-api.globalforestwatch.org"
GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA = {"User-Agent": "ForestWatchAI/1.0 (self-hosted deforestation monitoring)"}


class ProviderError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


EVALSCRIPT = """//VERSION=3
function setup(){return{input:[{bands:["B02","B03","B04","B08","B12","SCL","dataMask"],units:["REFLECTANCE","REFLECTANCE","REFLECTANCE","REFLECTANCE","REFLECTANCE","DN","DN"]}],
output:{bands:7,sampleType:"FLOAT32"}}}
function evaluatePixel(s){return [s.B02,s.B03,s.B04,s.B08,s.B12,s.SCL,s.dataMask];}"""

_tok = {"v": None, "exp": 0}
_tok_lock = threading.Lock()
_scene_cache = {}


def _token():
    if not settings.sh_configured:
        raise ProviderError("Satellite credentials missing. Set SH_CLIENT_ID and SH_CLIENT_SECRET in backend/.env.", 503)
    with _tok_lock:
        if _tok["v"] and time.time() < _tok["exp"] - 60:
            return _tok["v"]
        try:
            r = httpx.post(settings.sh_token_url, data={"grant_type": "client_credentials", "client_id": settings.sh_client_id,
                           "client_secret": settings.sh_client_secret}, timeout=TIMEOUT)
        except httpx.HTTPError as e:
            raise ProviderError(f"Could not reach the {settings.sh_provider} auth server: {e.__class__.__name__}")
        if r.status_code != 200:
            raise ProviderError(f"{settings.sh_provider} rejected the OAuth client ({r.status_code}). Check SH_CLIENT_ID / SH_CLIENT_SECRET and SH_PROVIDER.", 502)
        j = r.json()
        _tok.update(v=j["access_token"], exp=time.time() + j.get("expires_in", 300))
        return _tok["v"]


def grid_size(bbox, max_px=1024, target_m=10.0):
    import math
    w, s, e, n = bbox
    wm = (e - w) * 111_320 * math.cos(math.radians((s + n) / 2))
    hm = (n - s) * 110_574
    px_w, px_h = wm / target_m, hm / target_m
    k = min(1.0, max_px / max(px_w, px_h))
    return max(32, int(px_w * k)), max(32, int(px_h * k)), target_m / k


def fetch_scene(bbox, d_from: date, d_to: date, max_cloud: float):
    """Least-cloudy Sentinel-2 L2A mosaic within [d_from, d_to]. Returns (array HxWx7, meta)."""
    width, height, res = grid_size(bbox)
    key = (tuple(round(x, 5) for x in bbox), d_from, d_to, max_cloud)
    hit = _scene_cache.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1], hit[2]
    body = {
        "input": {"bounds": {"bbox": list(bbox), "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
                  "data": [{"type": "sentinel-2-l2a", "dataFilter": {
                      "timeRange": {"from": f"{d_from}T00:00:00Z", "to": f"{d_to}T23:59:59Z"},
                      "maxCloudCoverage": max_cloud, "mosaickingOrder": "leastCC"}}]},
        "output": {"width": width, "height": height, "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
        "evalscript": EVALSCRIPT,
    }
    try:
        r = httpx.post(f"{settings.sh_base}/api/v1/process", json=body, timeout=httpx.Timeout(120.0, connect=10.0),
                       headers={"Authorization": f"Bearer {_token()}", "Accept": "image/tiff"})
    except httpx.HTTPError as e:
        raise ProviderError(f"Satellite request failed: {e.__class__.__name__}")
    if r.status_code == 401:
        _tok["v"] = None
        raise ProviderError("Satellite service rejected the access token. Retry; if it persists check your OAuth client.", 502)
    if r.status_code == 429:
        raise ProviderError("Satellite service rate limit reached. Wait a minute and retry.", 429)
    if r.status_code != 200:
        raise ProviderError(f"Satellite service error {r.status_code}: {r.text[:200]}", 502)
    arr = tifffile.imread(io.BytesIO(r.content)).astype(np.float32)
    if arr.ndim == 3 and arr.shape[0] == 7 and arr.shape[-1] != 7:
        arr = np.moveaxis(arr, 0, -1)  # some TIFF writers return band-first
    if arr.ndim != 3 or arr.shape[-1] != 7:
        raise ProviderError("Unexpected image format returned by the satellite service.")
    meta = {"resolution_m": round(res, 1), "width": width, "height": height}
    if len(_scene_cache) > 6:
        _scene_cache.pop(min(_scene_cache, key=lambda k: _scene_cache[k][0]))
    _scene_cache[key] = (time.time(), arr, meta)
    return arr, meta


def search_products(bbox, d_from: date, d_to: date, max_cloud: float, top=40):
    """Copernicus Data Space OData catalogue (no auth needed for search)."""
    w, s, e, n = bbox
    poly = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
    flt = (f"Collection/Name eq 'SENTINEL-2' and contains(Name,'MSIL2A') and "
           f"OData.CSC.Intersects(area=geography'SRID=4326;{poly}') and "
           f"ContentDate/Start ge {d_from}T00:00:00.000Z and ContentDate/Start le {d_to}T23:59:59.000Z and "
           f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value le {max_cloud})")
    params = {"$filter": flt, "$orderby": "ContentDate/Start desc", "$top": top, "$expand": "Attributes"}
    try:
        r = httpx.get(CDSE_ODATA, params=params, timeout=TIMEOUT, headers=UA)
    except httpx.HTTPError as e:
        raise ProviderError(f"Copernicus catalogue unreachable: {e.__class__.__name__}")
    if r.status_code != 200:
        raise ProviderError(f"Copernicus catalogue error {r.status_code}: {r.text[:200]}")
    out = []
    for p in r.json().get("value", []):
        cc = next((a["Value"] for a in p.get("Attributes", []) if a.get("Name") == "cloudCover"), None)
        out.append({"id": p["Id"], "name": p["Name"], "date": p["ContentDate"]["Start"][:10],
                    "datetime": p["ContentDate"]["Start"], "cloud_cover": round(cc, 1) if cc is not None else None})
    return out


def gfw_tree_cover_loss(bbox):
    """Annual tree cover loss (UMD/Hansen) inside the bbox from the GFW Data API."""
    if not settings.gfw_api_key:
        raise ProviderError("GFW_API_KEY is not set. Create a key at globalforestwatch.org and add it to backend/.env.", 503)
    w, s, e, n = bbox
    geom = {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}
    sql = ("SELECT umd_tree_cover_loss__year AS year, SUM(area__ha) AS loss_ha FROM results "
           "WHERE umd_tree_cover_density_2000__threshold >= 30 GROUP BY umd_tree_cover_loss__year ORDER BY umd_tree_cover_loss__year")
    try:
        r = httpx.post(f"{GFW_API}/dataset/umd_tree_cover_loss/latest/query/json", json={"sql": sql, "geometry": geom},
                       headers={"x-api-key": settings.gfw_api_key, **UA}, timeout=httpx.Timeout(90.0, connect=10.0))
    except httpx.HTTPError as e:
        raise ProviderError(f"Global Forest Watch unreachable: {e.__class__.__name__}")
    if r.status_code in (401, 403):
        raise ProviderError("Global Forest Watch rejected the API key.", 502)
    if r.status_code != 200:
        raise ProviderError(f"Global Forest Watch error {r.status_code}: {r.text[:200]}")
    return [{"year": int(x["year"]), "loss_ha": round(float(x["loss_ha"]), 2)} for x in r.json().get("data", []) if x.get("year")]


def geocode(q, limit=6):
    try:
        r = httpx.get(NOMINATIM, params={"q": q, "format": "jsonv2", "limit": limit}, headers=UA, timeout=15)
    except httpx.HTTPError as e:
        raise ProviderError(f"Place search unreachable: {e.__class__.__name__}")
    if r.status_code != 200:
        raise ProviderError(f"Place search error {r.status_code}")
    return [{"name": x["display_name"], "lat": float(x["lat"]), "lon": float(x["lon"]),
             "bbox": [float(x["boundingbox"][2]), float(x["boundingbox"][0]), float(x["boundingbox"][3]), float(x["boundingbox"][1])]}
            for x in r.json()]


_status = {"t": 0, "v": None}


def api_status(force=False):
    if not force and _status["v"] and time.time() - _status["t"] < 60:
        return _status["v"]
    out = {}

    def probe(name, fn):
        t = time.time()
        try:
            msg = fn()
            out[name] = {"ok": True, "message": msg or "Connected", "ms": int((time.time() - t) * 1000)}
        except ProviderError as e:
            out[name] = {"ok": False, "message": str(e), "ms": int((time.time() - t) * 1000)}
        except Exception as e:
            out[name] = {"ok": False, "message": f"{e.__class__.__name__}", "ms": int((time.time() - t) * 1000)}

    def sh():
        _token()
        return f"Authenticated ({settings.sh_provider})"

    def cdse():
        r = httpx.get(CDSE_ODATA, params={"$top": 1}, timeout=15, headers=UA)
        if r.status_code != 200:
            raise ProviderError(f"Catalogue returned {r.status_code}")

    def gibs():
        d = date.today() - timedelta(days=3)
        r = httpx.get(f"{GIBS}/MODIS_Terra_CorrectedReflectance_TrueColor/default/{d}/GoogleMapsCompatible_Level9/0/0/0.jpg", timeout=15)
        if r.status_code != 200:
            raise ProviderError(f"Tile service returned {r.status_code}")

    def gfw():
        if not settings.gfw_api_key:
            raise ProviderError("GFW_API_KEY not set", 503)
        r = httpx.get(f"{GFW_API}/dataset/umd_tree_cover_loss/latest", headers={"x-api-key": settings.gfw_api_key, **UA}, timeout=15)
        if r.status_code != 200:
            raise ProviderError(f"Data API returned {r.status_code}")

    for n, f in (("sentinel_hub", sh), ("copernicus_catalogue", cdse), ("nasa_gibs", gibs), ("global_forest_watch", gfw)):
        probe(n, f)
    out["provider"] = settings.sh_provider
    _status.update(t=time.time(), v=out)
    return out
