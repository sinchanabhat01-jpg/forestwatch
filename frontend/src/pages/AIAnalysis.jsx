import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, bboxStr } from "../api";
import { Page, Card, Stat, Spinner, ErrorBox, Empty, DemoBanner, Legend, Img, fmt, chartTheme } from "../components/Ui.jsx";

export default function AIAnalysis() {
  const nav = useLocation();
  const [list, setList] = useState(null), [sel, setSel] = useState(nav.state?.id || null), [a, setA] = useState(null), [err, setErr] = useState("");
  const [gfw, setGfw] = useState(null), [gErr, setGErr] = useState(""), [th, setTh] = useState(null), [busy, setBusy] = useState(false), [base, setBase] = useState("truecolor");
  useEffect(() => { api.get("/api/analysis/history").then((r) => { setList(r); if (!sel && r[0]) setSel(r[0].id); }).catch((e) => setErr(e.message)); }, []);
  useEffect(() => {
    if (!sel) return; setA(null); setGfw(null); setGErr("");
    api.get(`/api/analysis/${sel}`).then((r) => { setA(r); setTh({ ndvi_forest_min: r.thresholds.ndvi_forest_min, ndvi_loss_max: r.thresholds.ndvi_loss_max, ndvi_drop_min: r.thresholds.ndvi_drop_min, ndvi_uncertain_drop: r.thresholds.ndvi_uncertain_drop }); }).catch((e) => setErr(e.message));
  }, [sel]);
  async function crossCheck() { setGErr(""); try { setGfw(await api.get(`/api/forest/loss?bbox=${bboxStr(a.bbox)}`)); } catch (e) { setGErr(e.message); } }
  async function rerun() {
    setBusy(true); setErr("");
    try { const r = await api.post("/api/analysis/detect", { bbox: a.bbox, before_date: a.before_date, after_date: a.after_date, location_id: a.location_id, place_name: a.place_name, demo: a.is_demo, thresholds: th });
      setList([r, ...list]); setSel(r.id); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  const classes = a && [["Suspected loss", a.loss_ha, "#ef4444"], ["Uncertain", a.uncertain_ha, "#facc15"], ["Probable fire", a.fire_ha, "#f97316"], ["Stable forest", Math.max(0, a.forest_area_ha - a.loss_ha - a.uncertain_ha - a.fire_ha), "#22c55e"]];
  return (
    <Page title="AI forest analysis" subtitle="A transparent rule-based pipeline (NDVI change + burn-scar check + cloud masking). No neural network is used, and the page says so wherever it matters.">
      <ErrorBox error={err} />
      {!list ? <Spinner text="Loading analyses…" /> : !list.length ? <Empty>No analyses yet. Run one on the Deforestation detection page first.</Empty> : <>
        <div className="mb-4 max-w-xl"><label className="label" htmlFor="s">Analysis</label>
          <select id="s" className="input" value={sel || ""} onChange={(e) => setSel(+e.target.value)}>{list.map((x) => <option key={x.id} value={x.id}>#{x.id} · {x.place_name} · {x.before_date} → {x.after_date}{x.is_demo ? " · DEMO" : ""}</option>)}</select></div>
        {!a ? <Spinner text="Loading…" /> : <div className="space-y-4">
          {a.is_demo && <DemoBanner />}
          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Change overlay" className="lg:col-span-2" right={<select aria-label="Base image" className="input w-36 py-1" value={base} onChange={(e) => setBase(e.target.value)}><option value="">True colour</option><option value="_false">False colour</option><option value="_ndvi">NDVI</option></select>}>
              <div className="relative"><Img src={a.images[`after${base ? base : ""}`]} alt="Recent image" className="w-full rounded-lg" /><Img src={a.images.overlay} alt="Classified change overlay" className="absolute left-0 top-0 w-full rounded-lg" /></div>
              <div className="mt-3"><Legend /></div>
            </Card>
            <div className="space-y-4">
              <Card title="Area by class (ha)"><div className="h-48"><ResponsiveContainer><BarChart data={classes.map(([n, v, c]) => ({ n, v: +v.toFixed(1), c }))} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid stroke={chartTheme.grid} horizontal={false} /><XAxis type="number" stroke={chartTheme.axis} fontSize={11} /><YAxis type="category" dataKey="n" stroke={chartTheme.axis} fontSize={11} width={95} />
                <Tooltip contentStyle={chartTheme.tip} /><Bar dataKey="v" name="ha" radius={[0, 4, 4, 0]} fill="#39ff88" shape={(p) => <rect {...p} fill={p.payload.c} />} /></BarChart></ResponsiveContainer></div></Card>
              <Stat label="Method" value="NDVI rules" note={a.method + " · no trained model, no model confidence"} tone="text-white" />
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Written analysis"><p className="whitespace-pre-line text-sm leading-relaxed text-white/80">{a.report_text}</p></Card>
            <Card title="Adjust thresholds and re-run">
              <div className="grid grid-cols-2 gap-2">{[["ndvi_forest_min", "Forest NDVI ≥"], ["ndvi_loss_max", "Loss NDVI ≤"], ["ndvi_drop_min", "Min NDVI drop"], ["ndvi_uncertain_drop", "Uncertain drop"]].map(([k, t]) =>
                <div key={k}><label className="label" htmlFor={k}>{t}</label><input id={k} type="number" step="0.01" min="0" max="1" className="input" value={th?.[k] ?? ""} onChange={(e) => setTh({ ...th, [k]: parseFloat(e.target.value) })} /></div>)}</div>
              <button className="btn mt-3" onClick={rerun} disabled={busy}>{busy ? "Re-running…" : "Re-run with these values"}</button>
              <p className="mt-2 text-xs text-white/45">Creates a new analysis; the original stays in your history.</p>
            </Card>
          </div>
          {!a.is_demo && <Card title="Independent check: Global Forest Watch" right={<button className="btn-ghost" onClick={crossCheck}>Load GFW tree-cover loss</button>}>
            <ErrorBox error={gErr} />
            {gfw ? <div className="h-52"><ResponsiveContainer><BarChart data={gfw.years}><CartesianGrid stroke={chartTheme.grid} vertical={false} /><XAxis dataKey="year" stroke={chartTheme.axis} fontSize={11} /><YAxis stroke={chartTheme.axis} fontSize={11} />
              <Tooltip contentStyle={chartTheme.tip} /><Bar dataKey="loss_ha" name="Loss (ha)" fill="#a3e635" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
              : <p className="text-sm text-white/55">Annual tree-cover loss (UMD/Hansen) for this same box, for context. GFW is annual and lags by months, so it will not match a single-pair comparison exactly.</p>}
          </Card>}
        </div>}
      </>}
    </Page>
  );
}
