// src/api.js
//const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const BASE = import.meta.env.VITE_API_BASE ?? "";

// ---------- helpers ----------
async function readError(r, fallback) {
  try {
    const j = await r.json();
    if (j?.detail) {
      // detail can be string or object
      return typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    }
    return JSON.stringify(j);
  } catch {
    return fallback;
  }
}

async function jget(path) {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) {
    const msg = await readError(r, `${path} failed`);
    throw new Error(msg);
  }
  return r.json();
}

async function jpost(path, body) {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const msg = await readError(r, `${path} failed`);
    throw new Error(msg);
  }
  return r.json();
}

async function jput(path, body) {
  const r = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const msg = await readError(r, `${path} failed`);
    throw new Error(msg);
  }
  return r.json();
}

// ✅ multipart upload helper (NO Content-Type header!)
async function jupload(path, file, fieldName = "file") {
  const fd = new FormData();
  fd.append(fieldName, file);

  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    body: fd,
  });

  if (!r.ok) {
    const msg = await readError(r, `${path} failed`);
    throw new Error(msg);
  }

  return r.json();
}

// ---------- API ----------
export const api = {
  health: () => jget("/health"),

  skuScores: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return jget(`/api/scores/sku${qs ? `?${qs}` : ""}`);
  },
  skuDetail: (sku) => jget(`/api/scores/sku/${encodeURIComponent(sku)}`),

  zoneScores: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return jget(`/api/scores/zone${qs ? `?${qs}` : ""}`);
  },
  userScores: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return jget(`/api/scores/user${qs ? `?${qs}` : ""}`);
  },

  recommendations: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return jget(`/api/recommendations${qs ? `?${qs}` : ""}`);
  },
  spikes: () => jget("/api/alerts/spikes"),

  investigationsList: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return jget(`/api/investigations${qs ? `?${qs}` : ""}`);
  },
  investigationsCreate: (payload) => jpost("/api/investigations", payload),
  investigationsUpdate: (id, payload) =>
    jput(`/api/investigations/${encodeURIComponent(id)}`, payload),

  // ✅ uploads
  uploadSkuMaster: (file) => jupload("/api/ingest/sku_master", file, "file"),
  uploadAdjustments: (file) => jupload("/api/ingest/adjustments", file, "file"),
};