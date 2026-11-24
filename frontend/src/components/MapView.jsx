import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { Search, Crosshair, Layers } from "lucide-react";
import { api } from "../api";

const SEV_COLOR = { LOW: "#38bdf8", MEDIUM: "#facc15", HIGH: "#fb923c", CRITICAL: "#ef4444" };
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/{time}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg";
const GFW = "https://tiles.globalforestwatch.org/umd_tree_cover_loss/latest/dynamic/{z}/{x}/{y}.png";
const toBounds = (b) => L.latLngBounds([b[1], b[0]], [b[3], b[2]]);

/** Interactive map. Pass onBBox to enable rectangle drawing. */
export default function MapView({ bbox, onBBox, points = [], rects = [], focus, overlay, height = 420, tools = true, onPick }) {
  const el = useRef(null), m = useRef({}), [coord, setCoord] = useState(null), [q, setQ] = useState("");
  const [hits, setHits] = useState([]), [err, setErr] = useState(""), [gibsOn, setGibsOn] = useState(false), [gfwOn, setGfwOn] = useState(false);
  const [gibsDate, setGibsDate] = useState(new Date(Date.now() - 3 * 864e5).toISOString().slice(0, 10));
  const cb = useRef({ onBBox, onPick }); cb.current = { onBBox, onPick };

  useEffect(() => {
    const map = L.map(el.current, { center: [-3.4, -60], zoom: 5, worldCopyJump: true });
    const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" });
    const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 19, attribution: "Imagery © Esri, Maxar, Earthstar Geographics" });
    sat.addTo(map);
    L.control.layers({ "Satellite": sat, "Standard map": osm }, {}, { position: "topright" }).addTo(map);
    m.current = { map, shapes: L.layerGroup().addTo(map), drawn: L.featureGroup().addTo(map), osm, sat,
      gibs: L.tileLayer(GIBS, { time: gibsDate, maxNativeZoom: 9, maxZoom: 19, opacity: 0.85, attribution: "NASA GIBS / EOSDIS" }),
      gfw: L.tileLayer(GFW, { maxZoom: 19, opacity: 0.8, attribution: "Global Forest Watch / UMD" }) };
    map.on("mousemove", (e) => setCoord(e.latlng));
    map.on("click", (e) => cb.current.onPick?.([e.latlng.lat, e.latlng.lng]));
    if (onBBox) {
      window.L = L;
      import("leaflet-draw").then(() => {
        if (!m.current.map) return;
        const ctl = new L.Control.Draw({ position: "topleft", draw: { rectangle: { shapeOptions: { color: "#39ff88", weight: 2 } }, polygon: false, polyline: false, circle: false, marker: false, circlemarker: false }, edit: false });
        map.addControl(ctl);
        map.on(L.Draw.Event.CREATED, (e) => {
          m.current.drawn.clearLayers(); m.current.drawn.addLayer(e.layer);
          const b = e.layer.getBounds(); cb.current.onBBox?.([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
        });
      });
    }
    setTimeout(() => map.invalidateSize(), 50);
    return () => { map.remove(); m.current = {}; };
  }, []);

  useEffect(() => { const { map, gibs } = m.current; if (!map) return; gibsOn ? gibs.addTo(map) : map.removeLayer(gibs); }, [gibsOn]);
  useEffect(() => { const { map, gfw } = m.current; if (!map) return; gfwOn ? gfw.addTo(map) : map.removeLayer(gfw); }, [gfwOn]);
  useEffect(() => { m.current.gibs?.setUrl(GIBS.replace("{time}", gibsDate)); m.current.gibs && (m.current.gibs.options.time = gibsDate); }, [gibsDate]);

  useEffect(() => {  // the selected area
    const { drawn, map } = m.current; if (!map) return;
    drawn.clearLayers();
    if (bbox) L.rectangle(toBounds(bbox), { color: "#39ff88", weight: 2, fillOpacity: 0.05 }).addTo(drawn);
  }, [bbox]);

  useEffect(() => {  // alerts + saved locations + overlay
    const { shapes, map } = m.current; if (!map) return;
    shapes.clearLayers();
    rects.forEach((r) => L.rectangle(toBounds(r.bbox), { color: "#a3e635", weight: 1.5, fillOpacity: 0.08 }).bindTooltip(r.name).addTo(shapes));
    points.forEach((p) => L.circleMarker([p.lat, p.lon], { radius: 6 + Math.min(10, Math.sqrt(p.loss_ha || 1)), color: SEV_COLOR[p.severity] || "#fff", fillOpacity: 0.55, weight: 2 })
      .bindPopup(`<b>${p.name}</b><br/>${p.severity}: ${Number(p.loss_ha).toFixed(1)} ha${p.demo ? "<br/><i>demo data</i>" : ""}`).addTo(shapes));
    if (overlay?.url) L.imageOverlay(overlay.url, toBounds(overlay.bounds), { opacity: overlay.opacity ?? 0.9 }).addTo(shapes);
  }, [points, rects, overlay]);

  useEffect(() => { if (focus && m.current.map) m.current.map.flyToBounds(toBounds(focus), { maxZoom: 14, duration: 0.8 }); }, [focus]);

  async function search(e) {
    e.preventDefault(); setErr(""); setHits([]);
    if (q.trim().length < 2) return;
    try { const r = await api.get(`/api/geocode?q=${encodeURIComponent(q)}`); r.length ? setHits(r) : setErr("No place found. Try a larger area name."); }
    catch (x) { setErr(x.message); }
  }
  const useView = () => { const b = m.current.map.getBounds(); cb.current.onBBox?.([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]); };

  return (
    <div className="relative overflow-hidden rounded-xl border border-white/10" style={{ height }}>
      <div ref={el} className="h-full w-full" role="application" aria-label="Interactive satellite map" />
      {tools && (
        <div className="absolute left-14 top-3 z-[1000] w-[min(340px,70%)]">
          <form onSubmit={search} className="flex gap-1">
            <input className="input bg-black/70" placeholder="Search country, state, city…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search places" />
            <button className="btn px-3" aria-label="Search"><Search className="h-4 w-4" /></button>
          </form>
          {err && <div className="mt-1 rounded bg-black/80 p-2 text-xs text-red-300">{err}</div>}
          {hits.length > 0 && <ul className="mt-1 max-h-48 overflow-auto rounded-lg bg-black/85 text-xs">
            {hits.map((h, i) => <li key={i}><button className="w-full px-3 py-2 text-left hover:bg-white/10" onClick={() => { m.current.map.flyToBounds(toBounds(h.bbox), { maxZoom: 13 }); setHits([]); }}>{h.name}</button></li>)}
          </ul>}
        </div>
      )}
      {tools && (
        <div className="absolute bottom-6 left-3 z-[1000] flex flex-wrap items-center gap-2 rounded-lg bg-black/75 p-2 text-xs">
          <Layers className="h-4 w-4 text-neon" />
          <label className="flex items-center gap-1"><input type="checkbox" checked={gfwOn} onChange={(e) => setGfwOn(e.target.checked)} />GFW tree-cover loss</label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={gibsOn} onChange={(e) => setGibsOn(e.target.checked)} />NASA GIBS daily</label>
          {gibsOn && <input type="date" className="input w-36 py-1" value={gibsDate} max={new Date().toISOString().slice(0, 10)} onChange={(e) => e.target.value && setGibsDate(e.target.value)} aria-label="GIBS date" />}
          {onBBox && <button className="btn-ghost py-1" onClick={useView}><Crosshair className="h-3.5 w-3.5" />Use current view</button>}
        </div>
      )}
      <div className="absolute bottom-6 right-3 z-[1000] rounded bg-black/75 px-2 py-1 font-mono text-xs">
        {coord ? `${coord.lat.toFixed(5)}, ${coord.lng.toFixed(5)}` : "Move over the map"}
      </div>
    </div>
  );
}
