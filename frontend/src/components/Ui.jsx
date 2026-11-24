import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, FlaskConical } from "lucide-react";
import { api } from "../api";

export const SEV = { LOW: "bg-sky-400/15 text-sky-300", MEDIUM: "bg-yellow-400/15 text-yellow-300", HIGH: "bg-orange-500/20 text-orange-300", CRITICAL: "bg-red-500/25 text-red-300" };
export const Badge = ({ children, cls = "bg-white/10 text-white/80" }) => <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
export const fmt = (v, d = 1) => (v == null || Number.isNaN(v) ? "n/a" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }));

export function Page({ title, subtitle, actions, children }) {
  return (
    <div className="mx-auto max-w-7xl p-4 md:p-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-bold md:text-3xl">{title}</h1>{subtitle && <p className="mt-1 max-w-2xl text-sm text-white/60">{subtitle}</p>}</div>
        {actions}
      </div>
      {children}
    </div>
  );
}
export const Card = ({ title, right, children, className = "" }) => (
  <section className={`glass p-4 ${className}`}>
    {(title || right) && <div className="mb-3 flex items-center justify-between gap-2"><h2 className="text-base font-bold">{title}</h2>{right}</div>}
    {children}
  </section>
);
export const Stat = ({ label, value, unit, note, tone = "text-neon" }) => (
  <div className="glass p-4">
    <div className="text-xs text-white/55">{label}</div>
    <div className={`mt-1 font-display text-3xl font-bold ${tone}`}>{value}<span className="ml-1 text-sm font-medium text-white/50">{unit}</span></div>
    {note && <div className="mt-1 text-xs text-white/45">{note}</div>}
  </div>
);
export const Spinner = ({ text }) => <div className="flex items-center gap-2 text-sm text-white/70"><Loader2 className="h-4 w-4 animate-spin" />{text}</div>;
export const ErrorBox = ({ error, children }) => error ? (
  <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-200">
    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><div className="flex-1">{error}{children}</div>
  </div>) : null;
export const DemoBanner = ({ children }) => (
  <div className="flex items-center gap-2 rounded-lg border border-yellow-400/40 bg-yellow-400/10 px-3 py-2 text-sm text-yellow-200">
    <FlaskConical className="h-4 w-4 shrink-0" /><span><b>Demo data.</b> {children || "Synthetic imagery generated locally. It does not show a real place."}</span>
  </div>
);
export const Empty = ({ children }) => <div className="rounded-lg border border-dashed border-white/15 p-6 text-center text-sm text-white/55">{children}</div>;

// Fetch an authenticated image into an object URL
export function useBlobUrl(path) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let live = true, u;
    setUrl(null);
    if (path) api.blob(path).then((b) => { if (live) { u = URL.createObjectURL(b); setUrl(u); } }).catch(() => {});
    return () => { live = false; if (u) URL.revokeObjectURL(u); };
  }, [path]);
  return url;
}
export const AuthImg = ({ path, alt, className }) => { const u = useBlobUrl(path); return u ? <img src={u} alt={alt} className={className} /> : <div className={`animate-pulse bg-white/5 ${className}`} aria-label="Loading image" />; };

export const defaultDates = () => {
  const after = new Date(Date.now() - 20 * 864e5), before = new Date(after.getTime() - 365 * 864e5);
  const f = (d) => d.toISOString().slice(0, 10);
  return { before: f(before), after: f(after) };
};
export const Legend = () => (
  <div className="flex flex-wrap gap-3 text-xs text-white/70">
    {[["#22c55e", "Stable vegetation"], ["#ef4444", "Suspected forest loss"], ["#facc15", "Uncertain / other change"], ["#f97316", "Probable fire scar"]].map(([c, t]) =>
      <span key={t} className="flex items-center gap-1.5"><i className="h-3 w-3 rounded-sm" style={{ background: c }} />{t}</span>)}
  </div>
);

export const Img = ({ src, alt, className }) => src?.startsWith("/api") ? <AuthImg path={src} alt={alt} className={className} /> : <img src={src} alt={alt} className={className} />;
export const SourceToggle = ({ value, onChange }) => (
  <div className="inline-flex rounded-lg border border-white/15 p-0.5 text-xs" role="group" aria-label="Data source">
    {[["all", "All"], ["real", "Real imagery"], ["demo", "Demo only"]].map(([v, t]) =>
      <button key={v} onClick={() => onChange(v)} className={`rounded-md px-3 py-1 ${value === v ? "bg-neon text-canopy-950" : "text-white/70"}`}>{t}</button>)}
  </div>
);
export const chartTheme = { grid: "rgba(255,255,255,.08)", axis: "#9ca3af", tip: { background: "#0b0d0c", border: "1px solid rgba(255,255,255,.15)", borderRadius: 8, fontSize: 12 } };
