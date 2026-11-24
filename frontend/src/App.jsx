import { createContext, useContext, useEffect, useState } from "react";
import { Routes, Route, NavLink } from "react-router-dom";
import { LayoutDashboard, Map, ScanSearch, BrainCircuit, BellRing, BarChart3, MapPin, Trees, Menu } from "lucide-react";
import Dashboard from "./pages/Dashboard.jsx";
import LiveMap from "./pages/LiveMap.jsx";
import Detect from "./pages/Detect.jsx";
import AIAnalysis from "./pages/AIAnalysis.jsx";
import Alerts from "./pages/Alerts.jsx";
import Analytics from "./pages/Analytics.jsx";
import Locations from "./pages/Locations.jsx";

const AuthCtx = createContext(null);
export const useAuth = () => useContext(AuthCtx);

const NAV = [
  ["/", "Dashboard", LayoutDashboard], ["/map", "Live map", Map], ["/detect", "Deforestation detection", ScanSearch],
  ["/ai", "AI forest analysis", BrainCircuit], ["/alerts", "Alerts", BellRing], ["/analytics", "Analytics & reports", BarChart3], ["/locations", "Monitored locations", MapPin],
];

function Shell({ children }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex h-full">
      <aside className={`fixed inset-y-0 left-0 z-[2000] w-64 transform border-r border-white/10 bg-canopy-950/95 p-4 backdrop-blur transition md:static md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="mb-6 flex items-center gap-2 px-2"><Trees className="h-6 w-6 text-neon" /><span className="font-display text-lg font-bold">ForestWatch AI</span></div>
        <nav className="space-y-1" aria-label="Main">
          {NAV.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}
              className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? "bg-neon/15 text-neon" : "text-white/70 hover:bg-white/5 hover:text-white"}`}>
              <Icon className="h-4 w-4" />{label}
            </NavLink>))}
        </nav>
        <div className="absolute inset-x-4 bottom-4 border-t border-white/10 px-2 pt-3 text-xs text-white/45">
          Local workspace · No account required
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="sticky top-0 z-[1500] flex items-center gap-2 border-b border-white/10 bg-char-900/90 p-3 backdrop-blur md:hidden">
          <button className="btn-ghost px-2" onClick={() => setOpen(!open)} aria-label="Toggle menu"><Menu className="h-5 w-5" /></button>
          <span className="font-display font-bold">ForestWatch AI</span>
        </div>
        {children}
      </main>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState({ id: 1, name: "Local user", email: "local@forestwatch", notify_email: false, smtp_configured: false });
  return (
    <AuthCtx.Provider value={{ user, setUser }}>
      <Shell><Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/map" element={<LiveMap />} />
        <Route path="/detect" element={<Detect />} />
        <Route path="/ai" element={<AIAnalysis />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/locations" element={<Locations />} />
        <Route path="*" element={<Dashboard />} />
      </Routes></Shell>
    </AuthCtx.Provider>
  );
}
