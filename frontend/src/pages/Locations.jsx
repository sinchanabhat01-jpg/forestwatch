import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Trash2, RefreshCw, History } from "lucide-react";
import { api } from "../api";
import { useAuth } from "../App.jsx";
import MapView from "../components/MapView.jsx";
import { Page, Card, Badge, Spinner, ErrorBox, Empty, fmt } from "../components/Ui.jsx";

const STATUS = { alert: "bg-red-500/20 text-red-300", ok: "bg-neon/15 text-neon", up_to_date: "bg-neon/15 text-neon", scheduled: "bg-sky-400/15 text-sky-300", error: "bg-red-500/20 text-red-300", no_clear_scene: "bg-yellow-400/15 text-yellow-300" };

export default function Locations() {
  const { user, setUser } = useAuth();
  const [rows, setRows] = useState(null), [bbox, setBbox] = useState(null), [name, setName] = useState(""), [err, setErr] = useState(""), [busy, setBusy] = useState(null), [focus, setFocus] = useState(null), [hist, setHist] = useState({});
  const load = () => api.get("/api/locations").then(setRows).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const upd = (l) => setRows((r) => r.map((x) => (x.id === l.id ? l : x)));
  async function add(e) { e.preventDefault(); setErr(""); try { await api.post("/api/locations", { name, bbox }); setName(""); setBbox(null); load(); } catch (x) { setErr(x.message); } }
  async function del(l) { if (!confirm(`Delete “${l.name}” and its analysis history?`)) return; try { await api.del(`/api/locations/${l.id}`); setRows(rows.filter((x) => x.id !== l.id)); } catch (x) { setErr(x.message); } }
  async function monitor(l, enabled, freq) { try { upd(await api.put(`/api/locations/${l.id}/monitoring`, { enabled, frequency_days: freq })); } catch (x) { setErr(x.message); } }
  async function check(l) { setBusy(l.id); setErr(""); try { upd((await api.post(`/api/locations/${l.id}/check`)).location); } catch (x) { setErr(x.message); } finally { setBusy(null); } }
  async function showHist(l) { try { setHist({ ...hist, [l.id]: await api.get(`/api/analysis/history?location_id=${l.id}`) }); } catch (x) { setErr(x.message); } }
  async function toggleEmail(v) { try { setUser(await api.put("/api/auth/me", { notify_email: v })); } catch (x) { setErr(x.message); } }
  return (
    <Page title="Monitored locations" subtitle="Save areas and let ForestWatch check for new Sentinel-2 scenes. Each check compares the newest clear scene with the same season one year earlier.">
      <ErrorBox error={err} />
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <MapView height={360} bbox={bbox} onBBox={setBbox} rects={(rows || []).map((l) => ({ name: l.name, bbox: l.bbox }))} focus={focus} />
        <div className="space-y-4">
          <Card title="Add a location"><form onSubmit={add} className="space-y-3">
            <div><label className="label" htmlFor="n">Name</label><input id="n" className="input" required maxLength={160} value={name} onChange={(e) => setName(e.target.value)} /></div>
            <p className="text-xs text-white/55">{bbox ? `Area drawn: W ${bbox[0].toFixed(3)} S ${bbox[1].toFixed(3)} E ${bbox[2].toFixed(3)} N ${bbox[3].toFixed(3)}` : "Draw a rectangle on the map to define the boundary."}</p>
            <button className="btn w-full" disabled={!bbox || !name.trim()}>Save location</button></form></Card>
          <Card title="Email alerts"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!user.notify_email} onChange={(e) => toggleEmail(e.target.checked)} />Email me when monitoring finds loss</label>
            {!user.smtp_configured && <p className="mt-1 text-xs text-white/50">Optional. SMTP is not configured on the server, so no emails will be sent yet.</p>}</Card>
        </div>
      </div>
      <div className="mt-4 space-y-3">
        {!rows ? <Spinner text="Loading…" /> : !rows.length ? <Empty>No locations yet. Draw an area above and save it.</Empty> : rows.map((l) => (
          <Card key={l.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><h3 className="text-lg font-bold">{l.name}</h3><p className="text-xs text-white/50">{fmt(l.area_ha, 0)} ha · added {l.created_at?.slice(0, 10)}</p></div>
              <div className="flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={l.monitoring_enabled} onChange={(e) => monitor(l, e.target.checked, l.frequency_days)} />Monitor every</label>
                <select aria-label="Frequency" className="input w-24 py-1" value={l.frequency_days} onChange={(e) => monitor(l, l.monitoring_enabled, +e.target.value)}>{[1, 3, 5, 7, 14, 30].map((d) => <option key={d} value={d}>{d} day{d > 1 ? "s" : ""}</option>)}</select>
                <button className="btn-ghost" onClick={() => check(l)} disabled={busy === l.id}><RefreshCw className={`h-4 w-4 ${busy === l.id ? "animate-spin" : ""}`} />Check now</button>
                <Link className="btn-ghost" to="/detect" state={{ bbox: l.bbox, locationId: l.id, name: l.name }}>Analyse dates</Link>
                <button className="btn-ghost" onClick={() => setFocus([...l.bbox])}>Show</button>
                <button className="btn-ghost" onClick={() => showHist(l)}><History className="h-4 w-4" />History</button>
                <button className="btn-ghost text-red-300" onClick={() => del(l)} aria-label={`Delete ${l.name}`}><Trash2 className="h-4 w-4" /></button></div>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div><dt className="text-xs text-white/50">Status</dt><dd><Badge cls={STATUS[l.monitoring_status]}>{l.monitoring_status.replace(/_/g, " ")}</Badge></dd></div>
              <div><dt className="text-xs text-white/50">Latest observation</dt><dd>{l.latest_observation || "none yet"}</dd></div>
              <div><dt className="text-xs text-white/50">Last checked</dt><dd>{l.last_checked_at ? new Date(l.last_checked_at + "Z").toLocaleString() : "never"}</dd></div>
              <div><dt className="text-xs text-white/50">Last analysis</dt><dd>{l.last_analysis_at ? new Date(l.last_analysis_at + "Z").toLocaleString() : "never"}</dd></div></dl>
            {l.monitoring_message && <p className="mt-2 text-xs text-white/55">{l.monitoring_message}</p>}
            {hist[l.id] && (hist[l.id].length ? <table className="mt-3 w-full"><thead><tr><th className="th">Compared</th><th className="th">Loss (ha)</th><th className="th">% forest</th><th className="th">Data</th></tr></thead><tbody>
              {hist[l.id].map((a) => <tr key={a.id} className="border-t border-white/5"><td className="td">{a.before_date} → {a.after_date}</td><td className="td">{fmt(a.loss_ha)}</td><td className="td">{fmt(a.loss_pct_of_forest, 2)}</td><td className="td">{a.is_demo ? "Demo" : "Sentinel-2"}</td></tr>)}</tbody></table> : <p className="mt-3 text-sm text-white/55">No analyses for this location yet.</p>)}
          </Card>))}
      </div>
    </Page>
  );
}
