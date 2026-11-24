import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell, Pie, PieChart } from "recharts";
import { Download } from "lucide-react";
import { api } from "../api";
import { Page, Card, Spinner, ErrorBox, Empty, SourceToggle, chartTheme, fmt } from "../components/Ui.jsx";

const COLORS = ["#39ff88", "#a3e635", "#facc15", "#fb923c", "#ef4444", "#38bdf8", "#c084fc", "#94a3b8"];
const Chart = ({ children, data }) => data?.length ? <div className="h-64"><ResponsiveContainer>{children}</ResponsiveContainer></div> : <Empty>No data for this filter yet.</Empty>;
const ax = <><CartesianGrid stroke={chartTheme.grid} vertical={false} /><Tooltip contentStyle={chartTheme.tip} /></>;

export default function Analytics() {
  const [s, setS] = useState(null), [src, setSrc] = useState("all"), [hist, setHist] = useState([]), [pick, setPick] = useState(""), [err, setErr] = useState("");
  useEffect(() => { setS(null); api.get(`/api/analytics/summary?source=${src}`).then(setS).catch((e) => setErr(e.message)); }, [src]);
  useEffect(() => { api.get("/api/analysis/history").then((r) => { setHist(r); if (r[0]) setPick(r[0].id); }).catch(() => {}); }, []);
  const dl = (p, n) => api.download(p, n).catch((e) => setErr(e.message));
  return (
    <Page title="Analytics and reports" subtitle="Aggregated from analyses saved in your account. Loss is the suspected loss between each pair of images, so overlapping analyses of the same area add up; treat totals as indicative." actions={<SourceToggle value={src} onChange={setSrc} />}>
      <ErrorBox error={err} />
      {!s ? <Spinner text="Crunching numbers…" /> : <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Monthly forest loss (ha)"><Chart data={s.monthly}><LineChart data={s.monthly}>{ax}<XAxis dataKey="month" stroke={chartTheme.axis} fontSize={11} /><YAxis stroke={chartTheme.axis} fontSize={11} /><Line type="monotone" dataKey="loss_ha" name="Loss (ha)" stroke="#39ff88" strokeWidth={2} dot={{ r: 3 }} /></LineChart></Chart></Card>
        <Card title="Yearly comparison (ha)"><Chart data={s.yearly}><BarChart data={s.yearly}>{ax}<XAxis dataKey="year" stroke={chartTheme.axis} fontSize={11} /><YAxis stroke={chartTheme.axis} fontSize={11} /><Bar dataKey="loss_ha" name="Loss (ha)" fill="#a3e635" radius={[4, 4, 0, 0]} /></BarChart></Chart></Card>
        <Card title="Forest cover of analysed areas (%)"><Chart data={s.forest_trend}><LineChart data={s.forest_trend}>{ax}<XAxis dataKey="date" stroke={chartTheme.axis} fontSize={11} /><YAxis domain={[0, 100]} stroke={chartTheme.axis} fontSize={11} /><Line type="monotone" dataKey="forest_pct" name="Forest %" stroke="#22c55e" strokeWidth={2} /></LineChart></Chart></Card>
        <Card title="Area-wise deforestation (ha)"><Chart data={s.by_area}><BarChart data={s.by_area} layout="vertical" margin={{ left: 30 }}><CartesianGrid stroke={chartTheme.grid} horizontal={false} /><Tooltip contentStyle={chartTheme.tip} /><XAxis type="number" stroke={chartTheme.axis} fontSize={11} /><YAxis type="category" dataKey="area" width={110} stroke={chartTheme.axis} fontSize={10} /><Bar dataKey="loss_ha" name="Loss (ha)" fill="#fb923c" radius={[0, 4, 4, 0]} /></BarChart></Chart></Card>
        <Card title="Most affected regions"><Chart data={s.by_area.filter((x) => x.loss_ha > 0)}><PieChart><Tooltip contentStyle={chartTheme.tip} /><Pie data={s.by_area.filter((x) => x.loss_ha > 0)} dataKey="loss_ha" nameKey="area" outerRadius={90} label={(e) => e.area.slice(0, 14)} labelLine={false} fontSize={10}>{s.by_area.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie></PieChart></Chart></Card>
        <Card title="Historical forest-change trend (all analyses)">
          {s.forest_trend.length ? <div className="max-h-64 overflow-auto"><table className="w-full"><thead><tr><th className="th">Date</th><th className="th">Place</th><th className="th">Forest %</th></tr></thead><tbody>
            {[...s.forest_trend].reverse().map((r, i) => <tr key={i} className="border-t border-white/5"><td className="td">{r.date}</td><td className="td">{r.place}</td><td className="td">{fmt(r.forest_pct)}</td></tr>)}</tbody></table></div> : <Empty>No analyses yet.</Empty>}</Card>
      </div>}
      <Card title="Download reports" className="mt-4">
        <div className="flex flex-wrap items-end gap-3">
          <button className="btn" onClick={() => dl(`/api/reports/csv?source=${src}`, "forestwatch_analyses.csv")}><Download className="h-4 w-4" />CSV of all analyses</button>
          <div><label className="label" htmlFor="pk">Single analysis</label><select id="pk" className="input min-w-64" value={pick} onChange={(e) => setPick(e.target.value)}>
            {hist.map((h) => <option key={h.id} value={h.id}>#{h.id} · {h.place_name} · {h.after_date}{h.is_demo ? " · DEMO" : ""}</option>)}</select></div>
          <button className="btn-ghost" disabled={!pick} onClick={() => dl(`/api/reports/pdf?analysis_id=${pick}`, `forestwatch_report_${pick}.pdf`)}><Download className="h-4 w-4" />PDF report</button>
          <button className="btn-ghost" disabled={!pick} onClick={() => dl(`/api/analysis/${pick}/image/comparison`, `comparison_${pick}.png`)}><Download className="h-4 w-4" />Comparison image</button>
        </div></Card>
    </Page>
  );
}
