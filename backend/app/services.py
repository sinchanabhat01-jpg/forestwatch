import io
import json
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from sqlalchemy.orm import Session
from . import analysis as an
from . import providers
from .config import settings
from .models import (User, MonitoredLocation, SatelliteImage, DeforestationAnalysis, DeforestationAlert, AnalysisHistory)


def thresholds(overrides=None):
    th = dict(ndvi_forest_min=settings.ndvi_forest_min, ndvi_loss_max=settings.ndvi_loss_max, ndvi_drop_min=settings.ndvi_drop_min,
              ndvi_uncertain_drop=settings.ndvi_uncertain_drop, nbr_burn_drop=settings.nbr_burn_drop, burn_max_nir=settings.burn_max_nir,
              min_patch_pixels=settings.min_patch_pixels)
    for k, v in (overrides or {}).items():
        if v is not None and k in th:
            th[k] = v
    return th


def sev_cfg():
    return dict(medium=settings.sev_medium, high=settings.sev_high, critical=settings.sev_critical)


def log(db: Session, user_id, action, detail=None, analysis_id=None):
    db.add(AnalysisHistory(user_id=user_id, action=action, detail=(detail or "")[:500], analysis_id=analysis_id))


def img_dir(analysis_id: int) -> Path:
    p = Path(settings.image_dir) / f"analysis_{analysis_id}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_scenes(bbox, before_date, after_date, max_cloud, window_days, demo):
    if demo:
        b, a = an.synthetic_pair()
        return b, a, {"before": {"from": before_date, "to": before_date}, "after": {"from": after_date, "to": after_date}, "resolution_m": None}
    wd = timedelta(days=window_days)
    b, mb = providers.fetch_scene(bbox, before_date - wd, before_date, max_cloud)
    a, ma = providers.fetch_scene(bbox, after_date - wd, after_date, max_cloud)
    return b, a, {"before": {"from": before_date - wd, "to": before_date}, "after": {"from": after_date - wd, "to": after_date}, "resolution_m": mb["resolution_m"]}


def _composite(b_png, a_png, o_png, path, labels):
    b, a = Image.open(io.BytesIO(b_png)).convert("RGB"), Image.open(io.BytesIO(a_png)).convert("RGB")
    o = Image.open(io.BytesIO(o_png)).convert("RGBA")
    a_ov = a.convert("RGBA"); a_ov.alpha_composite(o)
    w, h = b.size
    canvas = Image.new("RGB", (w * 2, h + 28), (10, 20, 14))
    canvas.paste(b, (0, 28)); canvas.paste(a_ov.convert("RGB"), (w, 28))
    d = ImageDraw.Draw(canvas)
    d.text((8, 8), labels[0], fill=(220, 255, 220)); d.text((w + 8, 8), labels[1], fill=(220, 255, 220))
    canvas.save(path, "PNG")


def run_detection(db: Session, user: User, bbox, before_date: date, after_date: date, max_cloud=None, window_days=30,
                  th_over=None, demo=False, location: MonitoredLocation | None = None, place=None, notify=True):
    max_cloud = settings.max_cloud if max_cloud is None else max_cloud
    th = thresholds(th_over)
    b, a, meta = get_scenes(bbox, before_date, after_date, max_cloud, window_days, demo)
    st, cls = an.detect(b, a, bbox, th)
    name = place or (location.name if location else None) or f"{(bbox[1]+bbox[3])/2:.3f}, {(bbox[0]+bbox[2])/2:.3f}"
    source = "demo-synthetic" if demo else "sentinel-2-l2a"
    rec = DeforestationAnalysis(
        user_id=user.id, location_id=location.id if location else None, bbox=list(bbox), place_name=name,
        before_date=before_date, after_date=after_date, thresholds=th, is_demo=demo,
        mean_ndvi_before=st["forest_mean_ndvi_before"], mean_ndvi_after=st["forest_mean_ndvi_after"],
        forest_area_ha=st["forest_area_ha"], loss_ha=st["loss_ha"], uncertain_ha=st["uncertain_ha"], fire_ha=st["fire_ha"],
        loss_pct_of_forest=st["loss_pct_of_forest"], valid_pixel_pct=st["valid_pixel_pct"], confidence=None,
        report_text=an.write_report(st, before_date, after_date, name, demo, th))
    db.add(rec); db.flush()
    d = img_dir(rec.id)
    pngs = {"before": an.true_color_png(b), "after": an.true_color_png(a), "before_ndvi": an.ndvi_png(b), "after_ndvi": an.ndvi_png(a),
            "before_false": an.false_color_png(b), "after_false": an.false_color_png(a), "overlay": an.overlay_png(cls)}
    for k, v in pngs.items():
        (d / f"{k}.png").write_bytes(v)
    _composite(pngs["before"], pngs["after"], pngs["overlay"], d / "comparison.png", (f"Before {before_date}", f"After {after_date} + loss overlay"))
    rec.overlay_path = str(d / "overlay.png")
    imgs = []
    for tag, dd in (("before", meta["before"]), ("after", meta["after"])):
        im = SatelliteImage(user_id=user.id, location_id=location.id if location else None, source=source, acquisition_from=dd["from"],
                            acquisition_to=dd["to"], bbox=list(bbox), file_path=str(d / f"{tag}.png"), is_demo=demo,
                            valid_pixel_pct=st["valid_pixel_pct"], cloud_cover_pct=round(100 - st["valid_pixel_pct"], 1))
        db.add(im); imgs.append(im)
    db.flush()
    rec.before_image_id, rec.after_image_id = imgs[0].id, imgs[1].id

    alert = None
    if st["loss_ha"] >= settings.alert_min_ha:
        alert = DeforestationAlert(user_id=user.id, analysis_id=rec.id, location_id=location.id if location else None, location_name=name,
                                   lat=(bbox[1] + bbox[3]) / 2, lon=(bbox[0] + bbox[2]) / 2, detection_date=after_date,
                                   loss_ha=st["loss_ha"], severity=an.severity(st["loss_ha"], sev_cfg()), is_demo=demo)
        db.add(alert)
    if location:
        location.last_analysis_at = datetime.utcnow()
    log(db, user.id, "detect" + ("_demo" if demo else ""), f"{name}: {st['loss_ha']:.1f} ha suspected loss", rec.id)
    db.commit()
    if alert and notify and not demo:
        send_alert_email(user, alert)
    return rec, st, alert, meta


def send_alert_email(user: User, alert: DeforestationAlert):
    if not (user.notify_email and settings.smtp_host):
        return
    try:
        m = EmailMessage()
        m["Subject"] = f"[ForestWatch] {alert.severity} forest-loss alert: {alert.location_name}"
        m["From"], m["To"] = settings.smtp_from, user.email
        m.set_content(f"Suspected forest loss of {alert.loss_ha:.1f} ha near {alert.lat:.4f}, {alert.lon:.4f} "
                      f"(detected for {alert.detection_date}). Review it in ForestWatch AI. This is an automated rule-based detection and needs verification.")
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(m)
    except Exception:
        pass  # email is optional; never fail an analysis because of it


def check_location(db: Session, loc: MonitoredLocation, user: User):
    """Look for a newer Sentinel-2 acquisition; analyse it against the same season one year earlier."""
    bbox = [loc.west, loc.south, loc.east, loc.north]
    loc.last_checked_at = datetime.utcnow()
    try:
        prods = providers.search_products(bbox, date.today() - timedelta(days=45), date.today(), settings.max_cloud, top=10)
    except providers.ProviderError as e:
        loc.monitoring_status, loc.monitoring_message = "error", str(e)[:390]
        db.commit(); return {"status": "error", "message": str(e)}
    if not prods:
        loc.monitoring_status, loc.monitoring_message = "no_clear_scene", f"No Sentinel-2 scene under {settings.max_cloud:.0f}% cloud in the last 45 days."
        db.commit(); return {"status": loc.monitoring_status, "message": loc.monitoring_message}
    newest = date.fromisoformat(prods[0]["date"])
    if loc.latest_observation and newest <= loc.latest_observation:
        loc.monitoring_status, loc.monitoring_message = "up_to_date", f"No new observation since {loc.latest_observation}."
        db.commit(); return {"status": "up_to_date", "message": loc.monitoring_message}
    try:
        rec, st, alert, _ = run_detection(db, user, bbox, newest - timedelta(days=365), newest, location=loc)
    except providers.ProviderError as e:
        loc.monitoring_status, loc.monitoring_message = "error", str(e)[:390]
        db.commit(); return {"status": "error", "message": str(e)}
    loc.latest_observation = newest
    loc.monitoring_status = "alert" if alert else "ok"
    loc.monitoring_message = f"Analysed observation of {newest}: {st['loss_ha']:.1f} ha suspected loss."
    db.commit()
    return {"status": loc.monitoring_status, "message": loc.monitoring_message, "analysis_id": rec.id}


def scheduler_tick():
    from .db import SessionLocal
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        for loc in db.query(MonitoredLocation).filter(MonitoredLocation.monitoring_enabled.is_(True)).all():
            if loc.last_checked_at and now - loc.last_checked_at < timedelta(days=loc.frequency_days):
                continue
            user = db.get(User, loc.user_id)
            if user:
                check_location(db, loc, user)
    finally:
        db.close()
