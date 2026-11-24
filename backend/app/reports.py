import csv
import io
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage

COLS = ["id", "place", "before_date", "after_date", "forest_area_ha", "loss_ha", "loss_pct_of_forest", "uncertain_ha", "fire_ha",
        "mean_ndvi_before", "mean_ndvi_after", "valid_pixel_pct", "method", "data_source"]


def analyses_csv(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLS)
    for r in rows:
        f = lambda v, n=3: "" if v is None else round(v, n)
        w.writerow([r.id, r.place_name, r.before_date, r.after_date, f(r.forest_area_ha, 2), f(r.loss_ha, 2), f(r.loss_pct_of_forest, 2),
                    f(r.uncertain_ha, 2), f(r.fire_ha, 2), f(r.mean_ndvi_before), f(r.mean_ndvi_after), f(r.valid_pixel_pct, 1), r.method,
                    "DEMO-SYNTHETIC" if r.is_demo else "Sentinel-2 L2A"])
    return buf.getvalue().encode("utf-8-sig")


def analysis_pdf(r, image_path: str | None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"ForestWatch analysis {r.id}")
    ss = getSampleStyleSheet()
    el = [Paragraph("ForestWatch AI - Forest change report", ss["Title"]),
          Paragraph(f"Analysis #{r.id} &nbsp; | &nbsp; {r.place_name or ''} &nbsp; | &nbsp; created {r.created_at:%Y-%m-%d %H:%M} UTC", ss["Normal"])]
    if r.is_demo:
        el += [Spacer(1, 4), Paragraph("<b><font color='#b91c1c'>DEMO DATA - synthetic imagery, not a real place.</font></b>", ss["Normal"])]
    el.append(Spacer(1, 8))
    n = lambda v, d=2: "n/a" if v is None else f"{v:.{d}f}"
    data = [["Measure", "Value"],
            ["Older image / recent image", f"{r.before_date} / {r.after_date}"],
            ["Forest area in older image (ha)", n(r.forest_area_ha, 1)],
            ["Suspected forest loss (ha)", n(r.loss_ha, 1)],
            ["Loss as % of forest", n(r.loss_pct_of_forest) + " %"],
            ["Uncertain change (ha)", n(r.uncertain_ha, 1)],
            ["Probable fire scar (ha)", n(r.fire_ha, 1)],
            ["Mean forest NDVI before / after", f"{n(r.mean_ndvi_before)} / {n(r.mean_ndvi_after)}"],
            ["Usable pixels", n(r.valid_pixel_pct, 1) + " %"],
            ["Method", r.method + " (rule-based, no trained model)"]]
    t = Table(data, colWidths=[75 * mm, 100 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14532d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white])]))
    el += [t, Spacer(1, 10)]
    if image_path and Path(image_path).exists():
        el += [RLImage(image_path, width=175 * mm, height=175 * mm * 0.5, kind="proportional"),
               Paragraph("Left: older image. Right: recent image with overlay (red = suspected loss, yellow = uncertain, orange = probable fire, green = stable forest).", ss["Italic"]),
               Spacer(1, 8)]
    el += [Paragraph("Analysis summary", ss["Heading3"])]
    for line in (r.report_text or "").split("\n"):
        el.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;"), ss["BodyText"]))
    doc.build(el)
    return buf.getvalue()
