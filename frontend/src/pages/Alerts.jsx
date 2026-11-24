import { useEffect, useState } from "react";
import { X, Eye, CheckCheck } from "lucide-react";
import { api } from "../api";
import MapView from "../components/MapView.jsx";
import { Page, Card, Badge, SEV, Spinner, ErrorBox, Empty, DemoBanner, Img, fmt } from "../components/Ui.jsx";

export default function Alerts() {
  const [rows, setRows] = useState(null), [locs, setLocs] = useState([]), [f, setF] = useState({ severity: "", location_id: "", status: "" }), [err, setErr] = useState(""), [open, setOpen] = useState(null), [focus, setFocus] = useState(null);
  const load = () => { const q = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString(); api.get(`/api/alerts?${q}`).then(setRows).catch((e) => setErr(e.message)); };
  useEffect(load, [f]);
  useEffect(() => { api.get("/api/locations").then(setLocs).catch(() => {}); }, []);
  async function review(id) { try { const u = await api.put(`/api/alerts/${id}/review`); setRows(rows.map((r) => (r.id === id ? u : r))); if (open?.id === id) setOpen({ ...open, ...u }); } catch (e) { setErr(e.message); } }
  async function view(a) { try { setOpen(await api.get(`/api/alerts/${a.id}`)); } catch (e) { setErr(e.message); } }
  const sel = (k, opts, label) => <div><label className="label" htmlFor={k}>{label}</label>
    <select id={k} className="input" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })}><option value="">All</option>{opts}</select></div>;
  return (
    <Page title="Deforestation alerts" subtitle="Alerts are created automatically when suspected loss in one analysis exceeds your configured minimum. Severity bands are set in the server .env.">
      <div className="mb-4 grid max-w-2xl grid-cols-3 gap-2">
        {sel("severity", ["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((s) => <option key={s}>{s}</option>), "Severity")}
        {sel("location_id", locs.map((l) => <option key={l.id} value={l.id}>{l.name}</option>), "Location")}
        {sel("status", ["NEW", "REVIEWED"].map((s) => <option key={s}>{s}</option>), "Status")}
      </div>
      <ErrorBox error={err} />
      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <Card>{!rows ? <Spinner text="Loading alerts…" /> : !rows.length ? <Empty>No alerts match. Alerts appear after a detection finds more loss than the minimum threshold.</Empty> :
          <div className="overflow-x-auto"><table className="w-full"><thead><tr><th className="th">ID</th><th className="th">Location</th><th className="th">Detected</th><th className="th">Loss (ha)</th><th className="th">Severity</th><th className="th">Status</th><th className="th" /></tr></thead>
            <tbody>{rows.map((a) => <tr key={a.id} className="border-t border-white/5">
              <td className="td font-mono text-xs">FW-{String(a.id).padStart(5, "0")}</td>
              <td className="td">{a.location_name}{a.is_demo && <Badge cls="ml-2 bg-yellow-400/15 text-yellow-300">demo</Badge>}</td>
              <td className="td">{a.detection_date}</td><td className="td">{fmt(a.loss_ha)}</td>
              <td className="td"><Badge cls={SEV[a.severity]}>{a.severity}</Badge></td>
              <td className="td"><Badge cls={a.status === "NEW" ? "bg-neon/15 text-neon" : ""}>{a.status}</Badge></td>
              <td className="td"><div className="flex gap-1"><button className="btn-ghost px-2 py-1" onClick={() => view(a)} aria-label="View details"><Eye className="h-4 w-4" /></button>
                <button className="btn-ghost px-2 py-1" onClick={() => setFocus([a.lon - 0.05, a.lat - 0.05, a.lon + 0.05, a.lat + 0.05])}>Map</button>
                {a.status === "NEW" && <button className="btn-ghost px-2 py-1" onClick={() => review(a.id)} aria-label="Mark reviewed"><CheckCheck className="h-4 w-4" /></button>}</div></td></tr>)}</tbody></table></div>}</Card>
        <Card title="Affected locations"><MapView tools={false} height={420} focus={focus} points={(rows || []).map((a) => ({ lat: a.lat, lon: a.lon, severity: a.severity, loss_ha: a.loss_ha, name: a.location_name, demo: a.is_demo }))} /></Card>
      </div>
      {open && <div className="fixed inset-0 z-[3000] grid place-items-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label="Alert details">
        <div className="glass max-h-[90vh] w-full max-w-3xl overflow-auto bg-char-800 p-5">
          <div className="mb-3 flex items-start justify-between"><div><h2 className="text-lg font-bold">FW-{String(open.id).padStart(5, "0")} · {open.location_name}</h2>
            <div className="mt-1 flex gap-2"><Badge cls={SEV[open.severity]}>{open.severity}</Badge><Badge>{open.status}</Badge></div></div>
            <button className="btn-ghost px-2" onClick={() => setOpen(null)} aria-label="Close"><X className="h-4 w-4" /></button></div>
          {open.is_demo && <div className="mb-3"><DemoBanner /></div>}
          <Img src={open.analysis.images.comparison} alt="Before and after comparison" className="w-full rounded-lg" />
          <dl className="mt-3 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
            {[["Suspected loss", `${fmt(open.loss_ha)} ha`], ["Of forest", `${fmt(open.analysis.loss_pct_of_forest, 2)} %`], ["Coordinates", `${open.lat.toFixed(4)}, ${open.lon.toFixed(4)}`], ["Compared", `${open.analysis.before_date} → ${open.analysis.after_date}`]].map(([k, v]) =>
              <div key={k}><dt className="text-xs text-white/50">{k}</dt><dd>{v}</dd></div>)}</dl>
          <p className="mt-3 whitespace-pre-line text-sm text-white/70">{open.analysis.report_text}</p>
          {open.status === "NEW" && <button className="btn mt-4" onClick={() => review(open.id)}>Mark as reviewed</button>}
        </div></div>}
    </Page>
  );
}
