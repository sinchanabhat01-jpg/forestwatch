import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Download, FlaskConical } from "lucide-react";
import { api, bboxStr } from "../api";
import MapView from "../components/MapView.jsx";
import { Page, Card, Stat, Spinner, ErrorBox, DemoBanner, Legend, Img, Badge, SEV, defaultDates, fmt } from "../components/Ui.jsx";

const TABS = [["truecolor", "True colour"], ["falsecolor", "False colour"], ["ndvi", "NDVI"]];
const KEY = { truecolor: "", falsecolor: "_false", ndvi: "_ndvi" };

export default function Detect() {
  const nav = useLocation(), d = defaultDates();
  const [bbox, setBbox] = useState(nav.state?.bbox || null), [locId, setLocId] = useState(nav.state?.locationId || null), [place, setPlace] = useState(nav.state?.name || "");
  const [before, setBefore] = useState(d.before), [after, setAfter] = useState(d.after), [cloud, setCloud] = useState(30), [win, setWin] = useState(30);
  const [th, setTh] = useState({ ndvi_forest_min: 0.6, ndvi_loss_max: 0.35, ndvi_drop_min: 0.25, ndvi_uncertain_drop: 0.15 });
  const [tab, setTab] = useState("truecolor"), [showOv, setShowOv] = useState(true), [busy, setBusy] = useState(""), [err, setErr] = useState(null);
  const [preview, setPreview] = useState(null), [res, setRes] = useState(null);

  const body = (extra = {}) => ({ bbox, before_date: before, after_date: after, max_cloud: cloud, window_days: win, ...extra });
  async function run(kind, demo = false) {
    setErr(null); setBusy(kind);
    try {
      if (kind === "preview") { setRes(null); setPreview(await api.post("/api/satellite/compare", body())); }
      else { setPreview(null); setRes(await api.post("/api/analysis/detect", body({ demo, location_id: locId, place_name: place || undefined, thresholds: th }))); }
    } catch (e) { setErr(e); } finally { setBusy(""); }
  }
  useEffect(() => { if (res) setTab("truecolor"); }, [res?.id]);

  const L = res ? res.images[`before${KEY[tab]}`] : preview?.before[tab], R = res ? res.images[`after${KEY[tab]}`] : preview?.after[tab];
  const thSet = (k) => (e) => setTh({ ...th, [k]: parseFloat(e.target.value) });
  const lossPct = res?.mean_ndvi_before != null ? (res.mean_ndvi_after - res.mean_ndvi_before) : null;

  return (
    <Page title="Deforestation detection" subtitle="Pick an area and two dates. Use the same season for both so natural leaf change is not mistaken for clearing.">
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="space-y-2">
          <MapView height={380} bbox={bbox} onBBox={(b) => { setBbox(b); setLocId(null); setRes(null); setPreview(null); }} />
          {bbox && <p className="font-mono text-xs text-white/50">W {bbox[0].toFixed(4)} S {bbox[1].toFixed(4)} E {bbox[2].toFixed(4)} N {bbox[3].toFixed(4)}{locId ? " · linked to a monitored location" : ""}</p>}
        </div>
        <Card title="Analysis settings">
          <div className="grid grid-cols-2 gap-2">
            <div><label className="label" htmlFor="b">Older image date</label><input id="b" type="date" className="input" value={before} onChange={(e) => setBefore(e.target.value)} /></div>
            <div><label className="label" htmlFor="a">Recent image date</label><input id="a" type="date" className="input" value={after} onChange={(e) => setAfter(e.target.value)} /></div>
            <div><label className="label" htmlFor="c">Max cloud cover %</label><input id="c" type="number" min="0" max="100" className="input" value={cloud} onChange={(e) => setCloud(+e.target.value)} /></div>
            <div><label className="label" htmlFor="w">Search window (days)</label><input id="w" type="number" min="1" max="120" className="input" value={win} onChange={(e) => setWin(+e.target.value)} /></div>
            <div className="col-span-2"><label className="label" htmlFor="p">Place name (optional)</label><input id="p" className="input" maxLength={200} value={place} onChange={(e) => setPlace(e.target.value)} /></div>
          </div>
          <details className="mt-3 text-sm"><summary className="cursor-pointer text-white/70">Detection thresholds</summary>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {[["ndvi_forest_min", "Forest NDVI ≥"], ["ndvi_loss_max", "Loss NDVI ≤"], ["ndvi_drop_min", "Min NDVI drop"], ["ndvi_uncertain_drop", "Uncertain drop"]].map(([k, t]) =>
                <div key={k}><label className="label" htmlFor={k}>{t}</label><input id={k} type="number" step="0.01" min="0" max="1" className="input" value={th[k]} onChange={thSet(k)} /></div>)}
            </div>
            <p className="mt-2 text-xs text-white/45">Defaults suit humid tropical forest. Dry forests and savanna usually need lower values; calibrate against a place you know.</p></details>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className="btn-ghost" disabled={!bbox || !!busy} onClick={() => run("preview")}>Preview images</button>
            <button className="btn" disabled={!bbox || !!busy} onClick={() => run("detect")}>Run detection</button>
          </div>
          {busy && <div className="mt-3"><Spinner text={busy === "preview" ? "Fetching both Sentinel-2 scenes…" : "Fetching scenes and analysing change…"} /></div>}
          {!bbox && <p className="mt-3 text-sm text-white/55">Draw an area on the map first.</p>}
        </Card>
      </div>

      {err && <div className="mt-4"><ErrorBox error={err.message}>
        {err.providerError && <div className="mt-2"><button className="btn-ghost" onClick={() => run("detect", true)}><FlaskConical className="h-4 w-4" />Run on synthetic demo data instead</button></div>}</ErrorBox></div>}

      {(res || preview) && <div className="mt-4 space-y-4">
        {res?.is_demo && <DemoBanner />}
        <Card title={res ? "Historical vs recent" : "Image preview (not yet analysed)"} right={
          <div className="flex items-center gap-2"><div className="inline-flex rounded-lg border border-white/15 p-0.5 text-xs">{TABS.map(([k, t]) =>
            <button key={k} onClick={() => setTab(k)} className={`rounded-md px-3 py-1 ${tab === k ? "bg-neon text-canopy-950" : "text-white/70"}`}>{t}</button>)}</div>
            {res && <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={showOv} onChange={(e) => setShowOv(e.target.checked)} />Loss overlay</label>}</div>}>
          <div className="grid gap-3 md:grid-cols-2">
            <figure><Img src={L} alt="Historical satellite image" className="w-full rounded-lg" /><figcaption className="mt-1 text-xs text-white/60">Historical · {res ? res.before_date : before}</figcaption></figure>
            <figure className="relative"><Img src={R} alt="Recent satellite image" className="w-full rounded-lg" />
              {res && showOv && <Img src={res.images.overlay} alt="Suspected change overlay" className="pointer-events-none absolute left-0 top-0 w-full rounded-lg" />}
              <figcaption className="mt-1 text-xs text-white/60">Recent · {res ? res.after_date : after}</figcaption></figure>
          </div>
          {res && <div className="mt-3"><Legend /></div>}
          {preview && <p className="mt-2 text-xs text-white/50">Mean NDVI {fmt(preview.before.mean_ndvi, 3)} → {fmt(preview.after.mean_ndvi, 3)} · usable pixels {fmt(preview.before.valid_pct, 0)}% / {fmt(preview.after.valid_pct, 0)}% · {preview.resolution_m} m per pixel</p>}
        </Card>

        {res && <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Suspected forest loss" value={fmt(res.loss_ha)} unit="ha" tone="text-red-400" note={`${fmt(res.loss_pct_of_forest, 2)}% of ${fmt(res.forest_area_ha, 0)} ha forest`} />
            <Stat label="Forest cover change" value={`-${fmt(res.loss_pct_of_forest, 2)}`} unit="%" tone="text-orange-300" />
            <Stat label="Forest NDVI before → after" value={`${fmt(res.mean_ndvi_before, 2)} → ${fmt(res.mean_ndvi_after, 2)}`} note="Mean over pixels that were forest" />
            <Stat label="Estimated affected area" value={fmt(res.loss_ha + res.uncertain_ha + res.fire_ha)} unit="ha" tone="text-yellow-300" note={`${fmt(res.loss_ha)} loss + ${fmt(res.uncertain_ha)} uncertain + ${fmt(res.fire_ha)} fire`} />
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Detection confidence"><p className="text-2xl font-bold text-white/70">Not available</p><p className="mt-1 text-sm text-white/55">{res.confidence_note}</p>
              <p className="mt-2 text-sm text-white/70">Data quality: {fmt(res.valid_pixel_pct, 0)}% of pixels usable in both images · {res.resolution_m ? `${res.resolution_m} m/pixel` : "synthetic grid"}</p></Card>
            <Card title="Summary" className="lg:col-span-2"><p className="whitespace-pre-line text-sm leading-relaxed text-white/80">{res.report_text}</p></Card>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {res.alert && <Badge cls={SEV[res.alert.severity]}>Alert created: {res.alert.severity}</Badge>}
            <Link className="btn-ghost" to="/ai" state={{ id: res.id }}>Open AI analysis</Link>
            <button className="btn-ghost" onClick={() => api.download(`/api/reports/pdf?analysis_id=${res.id}`, `forestwatch_report_${res.id}.pdf`)}><Download className="h-4 w-4" />PDF report</button>
            <button className="btn-ghost" onClick={() => api.download(res.images.comparison, `comparison_${res.id}.png`)}><Download className="h-4 w-4" />Comparison image</button>
            <button className="btn-ghost" onClick={() => api.download("/api/reports/csv", "forestwatch_analyses.csv")}><Download className="h-4 w-4" />CSV (all analyses)</button>
          </div></>}
      </div>}
    </Page>
  );
}
