# ForestWatch AI

Deforestation detection and forest monitoring from Sentinel-2 imagery.
React + Tailwind + Recharts + Leaflet frontend, FastAPI backend, MySQL.

## What it does

| Area | How it works |
|---|---|
| Imagery | Sentinel-2 L2A via the Sentinel Hub Process API. Works against **Copernicus Data Space (free)** or commercial Sentinel Hub (`SH_PROVIDER`). Least-cloudy mosaic in a date window, cloud-filtered. |
| Scene search | Copernicus Data Space OData catalogue (bbox, date range, cloud %). No key needed. |
| Detection | `NDVI = (B08 - B04) / (B08 + B04)` on both dates. Cloud, shadow, cirrus, snow and no-data pixels are masked with the Sentinel-2 scene classification layer (SCL). A pixel is **suspected loss** if it was forest (NDVI ≥ 0.60), fell by ≥ 0.25 and ended ≤ 0.35. Smaller drops are **uncertain** (possible seasonal change). Dark post-event pixels with a large NBR drop are **probable fire scars**, kept separate from clearing. Tiny clusters are removed. All thresholds are configurable. |
| Confidence | Not reported. This is a rule-based method with no validated model, so the app says "Not available" rather than inventing a number. |
| NASA GIBS | Daily MODIS true-colour tiles as a map layer with a date picker. |
| Global Forest Watch | Annual tree-cover loss (Data API) for any drawn area, plus the GFW loss tile layer on maps. |
| Alerts | Created when suspected loss ≥ `ALERT_MIN_HA`. Severity bands (LOW/MEDIUM/HIGH/CRITICAL) come from `.env`. Optional email via SMTP. |
| Monitoring | A scheduler checks saved locations every N days for a newer clear Sentinel-2 scene and compares it with the same season one year earlier. Sentinel-2 revisits about every 5 days; this is periodic monitoring, not live video. |
| Demo mode | If imagery is unavailable the UI offers a synthetic scene. Everything derived from it is flagged `is_demo`, labelled in the UI, and can be filtered out of the dashboard and analytics. |

## Folder structure

```
forestwatch/
├── backend/
│   ├── app/
│   │   ├── main.py        REST API, validation, auth wiring
│   │   ├── analysis.py    NDVI/NBR change detection, overlays, severity, report text
│   │   ├── providers.py   Sentinel Hub/CDSE, OData catalogue, GFW, GIBS probe, geocoding
│   │   ├── services.py    detection orchestration, alerts, email, monitoring scheduler
│   │   ├── reports.py     CSV + PDF
│   │   ├── security.py    bcrypt, JWT, rate limiting
│   │   ├── models.py  db.py  config.py
│   ├── sql/schema.sql     MySQL DDL (6 tables)
│   ├── tests/test_analysis.py
│   ├── requirements.txt   .env.example
└── frontend/              Vite + React (8 pages)
```

## Run it locally

Prerequisites: Python 3.11+, Node 18+, MySQL 8.

**1. Database**
```bash
mysql -u root -p < backend/sql/schema.sql
mysql -u root -p -e "CREATE USER 'forestwatch'@'localhost' IDENTIFIED BY 'change_me'; GRANT ALL ON forestwatch.* TO 'forestwatch'@'localhost';"
```

**2. Credentials** (all optional except the JWT secret, but imagery needs a satellite client)
- *Copernicus Data Space (recommended, free):* register at dataspace.copernicus.eu, open the dashboard at shapps.dataspace.copernicus.eu/dashboard, create an **OAuth client**, and copy the id/secret. Set `SH_PROVIDER=cdse`.
- *Sentinel Hub (commercial):* dashboard.sentinel-hub.com → User settings → OAuth clients. Set `SH_PROVIDER=sentinelhub`.
- *Global Forest Watch:* create an API key at globalforestwatch.org (see their "create and use an API key" guide) and set `GFW_API_KEY`.
- NASA GIBS needs no key.

**3. Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env     # then edit: DATABASE_URL, JWT_SECRET, SH_CLIENT_ID/SECRET, GFW_API_KEY
python -m pytest tests -q          # optional: pip install pytest; or python tests/test_analysis.py
uvicorn app.main:app --reload --port 8000
```
Check `http://localhost:8000/api/health` and the interactive docs at `/docs`.

**4. Frontend**
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```
Register an account, draw an area on **Deforestation detection**, choose two dates in the same season, and run it.
Production: `npm run build`, serve `dist/` behind the same host as the API, set `CORS_ORIGINS`, and run uvicorn with a single worker (the rate limiter and scheduler are in-process).

## API

`POST /api/auth/register|login` · `GET|PUT /api/auth/me` · `GET /api/status` · `GET /api/geocode` ·
`GET /api/satellite/search|image` · `POST /api/satellite/compare` · `GET /api/forest/loss` ·
`POST /api/analysis/detect` · `GET /api/analysis/history|{id}|{id}/image/{name}` ·
`GET /api/alerts` · `GET /api/alerts/{id}` · `PUT /api/alerts/{id}/review` ·
`GET|POST /api/locations` · `DELETE /api/locations/{id}` · `PUT /api/locations/{id}/monitoring` · `POST /api/locations/{id}/check` ·
`GET /api/analytics/summary` · `GET /api/reports/csv|pdf`

## Security

Secrets only in `backend/.env` (git-ignored). bcrypt password hashes, JWT bearer auth on every private route, per-user data scoping on every query, pydantic validation (bbox range/order/size, dates, cloud %), per-IP rate limits on login, imagery and detection, restricted CORS. The JWT is kept in `localStorage`, which is simple but readable by any XSS; move it to an httpOnly cookie if you harden this for production.

## Calibration and limits (read before trusting numbers)

- Defaults suit humid tropical forest. Dry forest, savanna, plantations and cropland need different NDVI thresholds. Calibrate against places you can verify.
- Compare the **same season** in both years; otherwise leaf-off or drought can look like loss. The "uncertain" class exists to catch part of this, not all of it.
- Area per request is capped at 100,000 ha and the image is capped at 1024 px on its long side, so large boxes are analysed at coarser than 10 m.
- Results are suspected change from a rule-based method. Confirm hotspots with high-resolution imagery or field data before acting.
