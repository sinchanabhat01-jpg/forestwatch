import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { api } from "../api";
import MapView from "../components/MapView.jsx";
import { Page, Card, Stat, Spinner, ErrorBox, Empty, Badge, SourceToggle, fmt, chartTheme } from "../components/Ui.jsx";

const NAMES = { sentinel_hub: "Sentinel Hub / imagery", copernicus_catalogue: "Copernicus catalogue", nasa_gibs: "NASA GIBS", global_forest_watch: "Global Forest Watch" };

export default function Dashboard() {
  const [s, setS] = useState(null), [locs, setLocs] = useState([]), [st, setSt] = useState(null), [src, setSrc] = useState("all"), [err, setErr] = useState(""), [chk, setChk] = useState(false);
  useEffect(() => { api.get(`/api/analytics/summary?source=${src}`).then(setS).catch((e) => setErr(e.message)); }, [src]);
  useEffect(() => { api.get("/api/locations").then(setLocs).catch(() => {}); loadStatus(false); }, []);
  const loadStatus = (refresh) => { setChk(true); api.get(`/api/status?refresh=${refresh}`).then(setSt).catch(() => {}).finally(() => setChk(false)); };
  if (err) return <Page title="Dashboard"><ErrorBox error={err} /></Page>;
  if (!s) return <Page title="Dashboard"><Spinner text="Loading your monitoring data…" /></Page>;
  return (
    <Page title="Forest monitoring overview" subtitle="Every figure comes from analyses saved in your database. Demo analyses are counted separately and labelled."
      actions={<SourceToggle value={src} onChange={setSrc} />}>
      {s.demo_count > 0 && src !== "real" && <p className="mb-4 rounded-lg bg-yellow-400/10 p-2 text-sm text-yellow-200">{s.demo_count} of {s.analysis_count} analyses shown here use synthetic demo data. Switch to “Real imagery” to exclude them.</p>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Forest analysed" value={fmt(s.forest_analysed_ha, 0)} unit="ha" note="Forest-like pixels in older images" />
        <Stat label="Suspected forest loss" value={fmt(s.total_loss_ha, 0)} unit="ha" tone="text-red-400" />
        <Stat label="Monitored locations" value={s.locations} note={`${fmt(s.monitored_area_ha, 0)} ha total`} />
        <Stat label="Active alerts" value={s.active_alerts} tone={s.active_alerts ? "text-orange-400" : "text-neon"} />
        <Stat label="Forest cover" value={s.forest_cover_pct == null ? "n/a" : fmt(s.forest_cover_pct)} unit={s.forest_cover_pct == null ? "" : "%"} note="Of analysed area" />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Monthly suspected forest loss (ha)" className="lg:col-span-2">
          {s.monthly.length ? <div className="h-64"><ResponsiveContainer><BarChart data={s.monthly}>
            <CartesianGrid stroke={chartTheme.grid} vertical={false} /><XAxis dataKey="month" stroke={chartTheme.axis} fontSize={11} /><YAxis stroke={chartTheme.axis} fontSize={11} />
            <Tooltip contentStyle={chartTheme.tip} cursor={{ fill: "rgba(255,255,255,.05)" }} /><Bar dataKey="loss_ha" name="Loss (ha)" fill="#39ff88" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
            : <Empty>No analyses yet. <Link className="text-neon underline" to="/detect">Run a detection</Link> to start filling this chart.</Empty>}
        </Card>
        <Card title="Data source status" right={<button className="btn-ghost px-2 py-1" onClick={() => loadStatus(true)} disabled={chk} aria-label="Recheck"><RefreshCw className={`h-4 w-4 ${chk ? "animate-spin" : ""}`} /></button>}>
          {!st ? <Spinner text="Checking services…" /> : <ul className="space-y-2.5 text-sm">
            {Object.keys(NAMES).map((k) => st[k] && <li key={k} className="flex items-start gap-2">
              {st[k].ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-neon" /> : <XCircle className="mt-0.5 h-4 w-4 text-red-400" />}
              <div><div>{NAMES[k]}</div><div className="text-xs text-white/50">{st[k].message}{st[k].ok ? ` · ${st[k].ms} ms` : ""}</div></div></li>)}
          </ul>}
          <p className="mt-3 text-xs text-white/45">Sentinel-2 revisits every ~5 days. Results are periodic observations, not live video.</p>
        </Card>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Global monitoring map" className="lg:col-span-2">
          <MapView tools={false} height={360} points={s.alert_points.filter((p) => src === "all" || (src === "demo") === p.demo)} rects={locs.map((l) => ({ name: l.name, bbox: l.bbox }))} />
        </Card>
        <Card title="Recent activity">
          {s.recent_activity.length ? <ul className="space-y-2 text-sm">{s.recent_activity.map((h) => <li key={h.id} className="border-b border-white/5 pb-2">
            <div className="flex items-center justify-between gap-2"><Badge>{h.action.replace(/_/g, " ")}</Badge><span className="text-xs text-white/40">{new Date(h.at + "Z").toLocaleString()}</span></div>
            <div className="mt-1 text-white/70">{h.detail}</div></li>)}</ul> : <Empty>Nothing yet.</Empty>}
        </Card>
      </div>
    </Page>
  );
}
