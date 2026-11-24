import { useState } from "react";
import { Link } from "react-router-dom";
import { api, bboxStr } from "../api";
import MapView from "../components/MapView.jsx";
import { Page, Card, ErrorBox, Spinner, defaultDates, fmt } from "../components/Ui.jsx";

export default function LiveMap() {
  const d = defaultDates();
  const [bbox, setBbox] = useState(null), [day, setDay] = useState(d.after), [layer, setLayer] = useState("truecolor"), [cloud, setCloud] = useState(30);
  const [overlay, setOverlay] = useState(null), [busy, setBusy] = useState(false), [err, setErr] = useState(""), [scenes, setScenes] = useState(null), [name, setName] = useState("");
  const [loss, setLoss] = useState(null), [saved, setSaved] = useState("");

  async function load() {
    setErr(""); setBusy(true); setOverlay(null);
    try {
      const blob = await api.blob(`/api/satellite/image?bbox=${bboxStr(bbox)}&day=${day}&layer=${layer}&max_cloud=${cloud}`);
      setOverlay({ url: URL.createObjectURL(blob), bounds: bbox, opacity: 1 });
      const start = new Date(new Date(day).getTime() - 60 * 864e5).toISOString().slice(0, 10);
      api.get(`/api/satellite/search?bbox=${bboxStr(bbox)}&start=${start}&end=${day}&max_cloud=${cloud}`).then((r) => setScenes(r.products)).catch(() => setScenes([]));
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  async function gfw() { setErr(""); setLoss(null); try { setLoss(await api.get(`/api/forest/loss?bbox=${bboxStr(bbox)}`)); } catch (e) { setErr(e.message); } }
  async function save() {
    try { await api.post("/api/locations", { name, bbox }); setSaved(`Saved “${name}”. Manage it under Monitored locations.`); setName(""); } catch (e) { setErr(e.message); }
  }
  return (
    <Page title="Live satellite map" subtitle="Search a place, draw a rectangle, then load the latest cloud-filtered Sentinel-2 image for it.">
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <MapView height={620} bbox={bbox} onBBox={(b) => { setBbox(b); setOverlay(null); setScenes(null); setLoss(null); setSaved(""); }} overlay={overlay} />
        <div className="space-y-4">
          <Card title="Selected area">
            {!bbox ? <p className="text-sm text-white/60">Use the square tool at the top-left of the map to draw an area (up to 100,000 ha), or press “Use current view”.</p> : <>
              <p className="font-mono text-xs text-white/70">W {bbox[0].toFixed(4)} · S {bbox[1].toFixed(4)}<br />E {bbox[2].toFixed(4)} · N {bbox[3].toFixed(4)}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div><label className="label" htmlFor="d">Image date (latest on or before)</label><input id="d" type="date" className="input" value={day} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setDay(e.target.value)} /></div>
                <div><label className="label" htmlFor="c">Max cloud %</label><input id="c" type="number" min="0" max="100" className="input" value={cloud} onChange={(e) => setCloud(+e.target.value)} /></div>
                <div className="col-span-2"><label className="label" htmlFor="l">Layer</label>
                  <select id="l" className="input" value={layer} onChange={(e) => setLayer(e.target.value)}><option value="truecolor">True colour (B04/B03/B02)</option><option value="falsecolor">False colour (B08/B04/B03)</option><option value="ndvi">NDVI vegetation index</option></select></div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2"><button className="btn" onClick={load} disabled={busy}>Load Sentinel-2 image</button><button className="btn-ghost" onClick={gfw}>GFW loss history</button><Link className="btn-ghost" to="/detect" state={{ bbox }}>Compare dates</Link></div>
              {busy && <div className="mt-3"><Spinner text="Requesting imagery…" /></div>}
            </>}
          </Card>
          <ErrorBox error={err} />
          {scenes && <Card title="Recent Sentinel-2 scenes (60 days)">
            {scenes.length ? <ul className="max-h-40 space-y-1 overflow-auto text-sm">{scenes.slice(0, 12).map((s) => <li key={s.id} className="flex justify-between"><span>{s.date}</span><span className="text-white/50">{fmt(s.cloud_cover, 0)}% cloud</span></li>)}</ul> : <p className="text-sm text-white/60">No scene under {cloud}% cloud in this window.</p>}</Card>}
          {loss && <Card title="Tree-cover loss by year (GFW)">
            <p className="mb-2 text-xs text-white/50">{loss.source}. Total {fmt(loss.total_ha, 0)} ha.</p>
            <ul className="max-h-40 space-y-1 overflow-auto text-sm">{loss.years.map((y) => <li key={y.year} className="flex justify-between"><span>{y.year}</span><span>{fmt(y.loss_ha, 0)} ha</span></li>)}</ul></Card>}
          {bbox && <Card title="Monitor this area">
            <div className="flex gap-2"><input className="input" placeholder="Location name" maxLength={160} value={name} onChange={(e) => setName(e.target.value)} aria-label="Location name" /><button className="btn" disabled={!name.trim()} onClick={save}>Save</button></div>
            {saved && <p className="mt-2 text-sm text-neon">{saved}</p>}</Card>}
        </div>
      </div>
    </Page>
  );
}
