import io
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import analysis as an, providers, reports, services
from .config import settings
from .db import Base, engine, get_db
from .models import (User, MonitoredLocation, SatelliteImage, DeforestationAnalysis, DeforestationAlert, AnalysisHistory)
from .security import hash_password, verify_password, make_token, current_user, rate_limit

MIN_DATE, MAX_AREA_HA = date(2017, 1, 1), 100_000


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    Path(settings.image_dir).mkdir(parents=True, exist_ok=True)
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(services.scheduler_tick, "interval", minutes=settings.tick_minutes, max_instances=1, coalesce=True)
    sched.start()
    yield
    sched.shutdown(wait=False)


app = FastAPI(title="ForestWatch AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])


@app.exception_handler(providers.ProviderError)
async def provider_error(_, e: providers.ProviderError):
    return JSONResponse({"detail": str(e), "provider_error": True}, status_code=e.status)


# ---------- validation helpers ----------
def check_bbox(b):
    if len(b) != 4 or not all(isinstance(x, (int, float)) for x in b):
        raise ValueError("bbox must be [west, south, east, north]")
    w, s, e, n = b
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("bbox out of range or not ordered west<east, south<north")
    ha = an.bbox_area_ha(b)
    if ha < 1: raise ValueError("Area is smaller than 1 ha")
    if ha > MAX_AREA_HA: raise ValueError(f"Area is {ha:,.0f} ha; the maximum is {MAX_AREA_HA:,} ha. Draw a smaller box.")
    return [float(x) for x in b]


def parse_bbox(s: str):
    try:
        return check_bbox([float(x) for x in s.split(",")])
    except ValueError as e:
        raise HTTPException(422, str(e))


def check_dates(before: date, after: date):
    if before >= after: raise ValueError("The older date must be before the recent date")
    if before < MIN_DATE: raise ValueError("Sentinel-2 L2A coverage starts in 2017")
    if after > date.today(): raise ValueError("The recent date cannot be in the future")


class BBoxModel(BaseModel):
    bbox: list[float]

    @field_validator("bbox")
    @classmethod
    def _b(cls, v): return check_bbox(v)


class Register(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)


class Login(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class Thresholds(BaseModel):
    ndvi_forest_min: Optional[float] = Field(None, ge=0.2, le=0.95)
    ndvi_loss_max: Optional[float] = Field(None, ge=0.0, le=0.8)
    ndvi_drop_min: Optional[float] = Field(None, ge=0.05, le=1.0)
    ndvi_uncertain_drop: Optional[float] = Field(None, ge=0.02, le=1.0)
    min_patch_pixels: Optional[int] = Field(None, ge=1, le=500)


class Compare(BBoxModel):
    before_date: date
    after_date: date
    max_cloud: float = Field(30, ge=0, le=100)
    window_days: int = Field(30, ge=1, le=120)

    @model_validator(mode="after")
    def _d(self):
        check_dates(self.before_date, self.after_date); return self


class Detect(Compare):
    location_id: Optional[int] = None
    place_name: Optional[str] = Field(None, max_length=200)
    thresholds: Optional[Thresholds] = None
    demo: bool = False


class LocationIn(BBoxModel):
    name: str = Field(min_length=1, max_length=160)


class MonitoringIn(BaseModel):
    enabled: bool
    frequency_days: int = Field(7, ge=1, le=60)


def uid_img(rec): return {k: f"/api/analysis/{rec.id}/image/{k}" for k in
                          ("before", "after", "before_ndvi", "after_ndvi", "before_false", "after_false", "overlay", "comparison")}


def analysis_out(r: DeforestationAnalysis, extra=None):
    d = {c: getattr(r, c) for c in ("id", "location_id", "bbox", "place_name", "method", "thresholds", "mean_ndvi_before", "mean_ndvi_after",
                                    "forest_area_ha", "loss_ha", "uncertain_ha", "fire_ha", "loss_pct_of_forest", "valid_pixel_pct", "confidence", "is_demo", "report_text")}
    d.update(before_date=str(r.before_date), after_date=str(r.after_date), created_at=r.created_at.isoformat() if r.created_at else None,
             total_area_ha=an.bbox_area_ha(r.bbox), images=uid_img(r),
             confidence_note="No validated model: this rule-based method does not report a statistical confidence.")
    d.update(extra or {})
    return d


def loc_out(l: MonitoredLocation):
    return {"id": l.id, "name": l.name, "bbox": [l.west, l.south, l.east, l.north], "area_ha": l.area_ha, "monitoring_enabled": l.monitoring_enabled,
            "frequency_days": l.frequency_days, "monitoring_status": l.monitoring_status, "monitoring_message": l.monitoring_message,
            "latest_observation": str(l.latest_observation) if l.latest_observation else None,
            "last_checked_at": l.last_checked_at.isoformat() if l.last_checked_at else None,
            "last_analysis_at": l.last_analysis_at.isoformat() if l.last_analysis_at else None,
            "created_at": l.created_at.isoformat() if l.created_at else None}


def alert_out(a: DeforestationAlert):
    return {"id": a.id, "analysis_id": a.analysis_id, "location_id": a.location_id, "location_name": a.location_name, "lat": a.lat, "lon": a.lon,
            "detection_date": str(a.detection_date), "loss_ha": a.loss_ha, "severity": a.severity, "status": a.status, "is_demo": a.is_demo,
            "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None, "created_at": a.created_at.isoformat() if a.created_at else None}


def own(db, model, id_, user):
    o = db.get(model, id_)
    if not o or o.user_id != user.id:
        raise HTTPException(404, "Not found.")
    return o


# ---------- system ----------
@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"ok": True, "database": "connected", "satellite_credentials": settings.sh_configured, "gfw_key": bool(settings.gfw_api_key)}


@app.get("/api/status")
def status(refresh: bool = False, user=Depends(current_user)):
    return providers.api_status(force=refresh)


# ---------- auth ----------
@app.post("/api/auth/register", status_code=201, dependencies=[Depends(rate_limit("auth", 10))])
def register(p: Register, db: Session = Depends(get_db)):
    u = User(email=p.email.lower(), name=p.name.strip(), password_hash=hash_password(p.password))
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "An account with this email already exists.")
    return {"token": make_token(u.id), "user": {"id": u.id, "name": u.name, "email": u.email, "notify_email": u.notify_email}}


@app.post("/api/auth/login", dependencies=[Depends(rate_limit("auth", 10))])
def login(p: Login, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == p.email.lower()))
    if not u or not verify_password(p.password, u.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    return {"token": make_token(u.id), "user": {"id": u.id, "name": u.name, "email": u.email, "notify_email": u.notify_email}}


@app.get("/api/auth/me")
def me(u: User = Depends(current_user)):
    return {"id": u.id, "name": u.name, "email": u.email, "notify_email": u.notify_email, "smtp_configured": bool(settings.smtp_host)}


@app.put("/api/auth/me")
def update_me(body: dict, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if "notify_email" in body:
        u.notify_email = bool(body["notify_email"]); db.commit()
    return me(u)


# ---------- search / satellite ----------
@app.get("/api/geocode")
def geocode(q: str = Query(min_length=2, max_length=120), user=Depends(current_user)):
    return providers.geocode(q)


@app.get("/api/satellite/search")
def sat_search(bbox: str, start: date, end: date, max_cloud: float = Query(30, ge=0, le=100), user=Depends(current_user)):
    if start > end or start < MIN_DATE:
        raise HTTPException(422, "Invalid date range.")
    return {"products": providers.search_products(parse_bbox(bbox), start, end, max_cloud)}


@app.get("/api/satellite/image", dependencies=[Depends(rate_limit("img", 30))])
def sat_image(bbox: str, day: date, layer: str = Query("truecolor", pattern="^(truecolor|falsecolor|ndvi)$"),
              max_cloud: float = Query(30, ge=0, le=100), window_days: int = Query(30, ge=1, le=120), user=Depends(current_user)):
    if day > date.today() or day < MIN_DATE:
        raise HTTPException(422, "Date out of range.")
    arr, meta = providers.fetch_scene(parse_bbox(bbox), day - timedelta(days=window_days), day, max_cloud)
    png = {"truecolor": an.true_color_png, "falsecolor": an.false_color_png, "ndvi": an.ndvi_png}[layer](arr)
    return Response(png, media_type="image/png", headers={"X-Resolution-M": str(meta["resolution_m"])})


@app.post("/api/satellite/compare", dependencies=[Depends(rate_limit("compare", 10))])
def sat_compare(p: Compare, db: Session = Depends(get_db), user: User = Depends(current_user)):
    import base64
    b, a, meta = services.get_scenes(p.bbox, p.before_date, p.after_date, p.max_cloud, p.window_days, False)
    enc = lambda x: "data:image/png;base64," + base64.b64encode(x).decode()
    vb, va = an.valid_mask(b), an.valid_mask(a)
    services.log(db, user.id, "compare", f"{p.before_date} vs {p.after_date}"); db.commit()
    return {"before": {"truecolor": enc(an.true_color_png(b)), "falsecolor": enc(an.false_color_png(b)), "ndvi": enc(an.ndvi_png(b)),
                       "mean_ndvi": float(an.ndvi(b)[vb].mean()) if vb.any() else None, "valid_pct": float(vb.mean() * 100), "window": [str(meta["before"]["from"]), str(meta["before"]["to"])]},
            "after": {"truecolor": enc(an.true_color_png(a)), "falsecolor": enc(an.false_color_png(a)), "ndvi": enc(an.ndvi_png(a)),
                      "mean_ndvi": float(an.ndvi(a)[va].mean()) if va.any() else None, "valid_pct": float(va.mean() * 100), "window": [str(meta["after"]["from"]), str(meta["after"]["to"])]},
            "resolution_m": meta["resolution_m"], "is_demo": False}


@app.get("/api/forest/loss")
def forest_loss(bbox: str, user=Depends(current_user)):
    rows = providers.gfw_tree_cover_loss(parse_bbox(bbox))
    return {"source": "Global Forest Watch / UMD Hansen tree cover loss (canopy >= 30% in 2000)", "years": rows, "total_ha": round(sum(r["loss_ha"] for r in rows), 1)}


# ---------- analysis ----------
@app.post("/api/analysis/detect", dependencies=[Depends(rate_limit("detect", 10))])
def detect(p: Detect, db: Session = Depends(get_db), user: User = Depends(current_user)):
    loc = own(db, MonitoredLocation, p.location_id, user) if p.location_id else None
    th = p.thresholds.model_dump() if p.thresholds else None
    rec, st, alert, meta = services.run_detection(db, user, p.bbox, p.before_date, p.after_date, p.max_cloud, p.window_days, th, p.demo, loc, p.place_name)
    return analysis_out(rec, {"alert": alert_out(alert) if alert else None, "resolution_m": meta["resolution_m"],
                              "forest_mean_ndvi_before": st["forest_mean_ndvi_before"], "scene_mean_ndvi_before": st["mean_ndvi_before"],
                              "scene_mean_ndvi_after": st["mean_ndvi_after"]})


@app.get("/api/analysis/history")
def history(location_id: Optional[int] = None, limit: int = Query(50, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(DeforestationAnalysis).where(DeforestationAnalysis.user_id == user.id)
    if location_id: q = q.where(DeforestationAnalysis.location_id == location_id)
    rows = db.scalars(q.order_by(DeforestationAnalysis.created_at.desc()).limit(limit)).all()
    return [analysis_out(r) for r in rows]


@app.get("/api/analysis/{aid}")
def get_analysis(aid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return analysis_out(own(db, DeforestationAnalysis, aid, user))


@app.get("/api/analysis/{aid}/image/{name}")
def analysis_image(aid: int, name: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    own(db, DeforestationAnalysis, aid, user)
    if name not in uid_img(type("R", (), {"id": aid})()):
        raise HTTPException(404, "Unknown image.")
    f = services.img_dir(aid) / f"{name}.png"
    if not f.exists(): raise HTTPException(404, "Image missing.")
    return FileResponse(f, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


# ---------- alerts ----------
@app.get("/api/alerts")
def alerts(severity: Optional[str] = Query(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$"), location_id: Optional[int] = None,
           status: Optional[str] = Query(None, pattern="^(NEW|REVIEWED)$"), db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(DeforestationAlert).where(DeforestationAlert.user_id == user.id)
    if severity: q = q.where(DeforestationAlert.severity == severity)
    if location_id: q = q.where(DeforestationAlert.location_id == location_id)
    if status: q = q.where(DeforestationAlert.status == status)
    return [alert_out(a) for a in db.scalars(q.order_by(DeforestationAlert.created_at.desc()).limit(500)).all()]


@app.get("/api/alerts/{aid}")
def alert_detail(aid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    a = own(db, DeforestationAlert, aid, user)
    return {**alert_out(a), "analysis": analysis_out(db.get(DeforestationAnalysis, a.analysis_id))}


@app.put("/api/alerts/{aid}/review")
def review_alert(aid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    a = own(db, DeforestationAlert, aid, user)
    a.status, a.reviewed_at = "REVIEWED", datetime.utcnow()
    services.log(db, user.id, "alert_reviewed", f"Alert {a.id} ({a.location_name})", a.analysis_id)
    db.commit()
    return alert_out(a)


# ---------- locations & monitoring ----------
@app.get("/api/locations")
def locations(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [loc_out(l) for l in db.scalars(select(MonitoredLocation).where(MonitoredLocation.user_id == user.id).order_by(MonitoredLocation.created_at.desc()))]


@app.post("/api/locations", status_code=201)
def add_location(p: LocationIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if db.scalar(select(func.count()).select_from(MonitoredLocation).where(MonitoredLocation.user_id == user.id)) >= 50:
        raise HTTPException(409, "Location limit (50) reached. Delete one first.")
    w, s, e, n = p.bbox
    l = MonitoredLocation(user_id=user.id, name=p.name.strip(), west=w, south=s, east=e, north=n, area_ha=an.bbox_area_ha(p.bbox))
    db.add(l); services.log(db, user.id, "location_added", l.name); db.commit()
    return loc_out(l)


@app.delete("/api/locations/{lid}", status_code=204)
def delete_location(lid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    l = own(db, MonitoredLocation, lid, user)
    services.log(db, user.id, "location_deleted", l.name)
    db.delete(l); db.commit()


@app.put("/api/locations/{lid}/monitoring")
def set_monitoring(lid: int, p: MonitoringIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    l = own(db, MonitoredLocation, lid, user)
    l.monitoring_enabled, l.frequency_days = p.enabled, p.frequency_days
    l.monitoring_status = "scheduled" if p.enabled else "idle"
    l.monitoring_message = (f"Checks for new Sentinel-2 scenes every {p.frequency_days} day(s). Sentinel-2 revisits each point about every 5 days, so this is periodic monitoring, not live video."
                            if p.enabled else "Monitoring paused.")
    db.commit()
    return loc_out(l)


@app.post("/api/locations/{lid}/check", dependencies=[Depends(rate_limit("check", 6))])
def check_now(lid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    l = own(db, MonitoredLocation, lid, user)
    res = services.check_location(db, l, user)
    services.log(db, user.id, "monitor_check", f"{l.name}: {res['status']}")
    db.commit()
    return {"result": res, "location": loc_out(l)}


# ---------- analytics & reports ----------
def _rows(db, user, source):
    q = select(DeforestationAnalysis).where(DeforestationAnalysis.user_id == user.id)
    if source == "real": q = q.where(DeforestationAnalysis.is_demo.is_(False))
    if source == "demo": q = q.where(DeforestationAnalysis.is_demo.is_(True))
    return db.scalars(q.order_by(DeforestationAnalysis.after_date)).all()


@app.get("/api/analytics/summary")
def summary(source: str = Query("all", pattern="^(all|real|demo)$"), db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = _rows(db, user, source)
    locs = db.scalars(select(MonitoredLocation).where(MonitoredLocation.user_id == user.id)).all()
    active = db.scalar(select(func.count()).select_from(DeforestationAlert).where(DeforestationAlert.user_id == user.id, DeforestationAlert.status == "NEW"))
    monthly, yearly, area, trend = defaultdict(float), defaultdict(float), defaultdict(float), []
    for r in rows:
        monthly[r.after_date.strftime("%Y-%m")] += r.loss_ha
        yearly[str(r.after_date.year)] += r.loss_ha
        area[r.place_name or "Unnamed"] += r.loss_ha
        tot = an.bbox_area_ha(r.bbox)
        trend.append({"date": str(r.after_date), "forest_pct": round(100 * r.forest_area_ha / tot, 1) if tot else 0, "place": r.place_name})
    forest = sum(r.forest_area_ha for r in rows); total = sum(an.bbox_area_ha(r.bbox) for r in rows)
    recent = db.scalars(select(AnalysisHistory).where(AnalysisHistory.user_id == user.id).order_by(AnalysisHistory.created_at.desc()).limit(10)).all()
    return {"source": source, "analysis_count": len(rows), "demo_count": sum(r.is_demo for r in rows),
            "monitored_area_ha": sum(l.area_ha for l in locs), "locations": len(locs), "active_alerts": active,
            "total_loss_ha": sum(r.loss_ha for r in rows), "forest_analysed_ha": forest,
            "forest_cover_pct": round(100 * forest / total, 1) if total else None,
            "monthly": [{"month": k, "loss_ha": round(v, 1)} for k, v in sorted(monthly.items())],
            "yearly": [{"year": k, "loss_ha": round(v, 1)} for k, v in sorted(yearly.items())],
            "by_area": sorted([{"area": k, "loss_ha": round(v, 1)} for k, v in area.items()], key=lambda x: -x["loss_ha"])[:10],
            "forest_trend": trend[-40:],
            "recent_activity": [{"id": h.id, "action": h.action, "detail": h.detail, "at": h.created_at.isoformat(), "analysis_id": h.analysis_id} for h in recent],
            "alert_points": [{"id": a.id, "lat": a.lat, "lon": a.lon, "severity": a.severity, "loss_ha": a.loss_ha, "name": a.location_name, "demo": a.is_demo}
                             for a in db.scalars(select(DeforestationAlert).where(DeforestationAlert.user_id == user.id).limit(300))]}


@app.get("/api/reports/csv")
def report_csv(source: str = Query("all", pattern="^(all|real|demo)$"), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return Response(reports.analyses_csv(_rows(db, user, source)), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="forestwatch_analyses.csv"'})


@app.get("/api/reports/pdf")
def report_pdf(analysis_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = own(db, DeforestationAnalysis, analysis_id, user)
    pdf = reports.analysis_pdf(r, str(services.img_dir(r.id) / "comparison.png"))
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="forestwatch_report_{r.id}.pdf"'})
