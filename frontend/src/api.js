// All calls go through the backend; no third-party key ever exists in the browser.
const BASE = import.meta.env.VITE_API_URL || "";
let token = localStorage.getItem("fw_token");
export const setToken = (t) => { token = t; t ? localStorage.setItem("fw_token", t) : localStorage.removeItem("fw_token"); };
export const hasToken = () => !!token;
let onAuthLost = () => {};
export const setAuthLostHandler = (f) => { onAuthLost = f; };

async function req(method, path, body, raw) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Cannot reach the ForestWatch server. Is the backend running on port 8000?");
  }
  if (res.status === 401 && token && !path.startsWith("/api/auth/login")) { setToken(null); onAuthLost(); }
  if (!res.ok) {
    let d = {};
    try { d = await res.json(); } catch {}
    const detail = Array.isArray(d.detail) ? d.detail.map((x) => x.msg).join("; ") : d.detail;
    const e = new Error(detail || `Request failed (${res.status})`);
    e.providerError = !!d.provider_error;
    throw e;
  }
  if (res.status === 204) return null;
  return raw ? res.blob() : res.json();
}
export const api = {
  get: (p) => req("GET", p), post: (p, b) => req("POST", p, b ?? {}), put: (p, b) => req("PUT", p, b ?? {}), del: (p) => req("DELETE", p),
  blob: (p) => req("GET", p, null, true),
  async download(path, filename) {
    const b = await req("GET", path, null, true);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  },
};
export const bboxStr = (b) => b.map((x) => x.toFixed(6)).join(",");
