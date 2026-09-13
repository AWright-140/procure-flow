import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// ── Tenders ──────────────────────────────────────────────────────────────────
export const fetchTenders = (params) =>
  api.get("/tenders", { params }).then((r) => r.data);

export const fetchTender = (id) =>
  api.get(`/tenders/${id}`).then((r) => r.data);

export const deleteTender = (id) =>
  api.delete(`/tenders/${id}`).then((r) => r.data);

// ── Stats ─────────────────────────────────────────────────────────────────────
export const fetchStats = () =>
  api.get("/stats").then((r) => r.data);

// ── Filters ───────────────────────────────────────────────────────────────────
export const fetchAgencies = () =>
  api.get("/filters/agencies").then((r) => r.data);

export const fetchCategories = () =>
  api.get("/filters/categories").then((r) => r.data);

// ── Scrape ────────────────────────────────────────────────────────────────────
export const triggerScrape = () =>
  api.post("/scrape").then((r) => r.data);

export const fetchScrapeRuns = (limit = 20) =>
  api.get("/scrape/runs", { params: { limit } }).then((r) => r.data);

// ── Export ────────────────────────────────────────────────────────────────────
export function buildExportUrl(format, filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v != null && v !== "") params.set(k, v);
  });
  const qs = params.toString();
  return `/api/export/${format}${qs ? "?" + qs : ""}`;
}

export const downloadTenderPdf = (id) =>
  window.open(`/api/tenders/${id}/pdf`, "_blank");

export const batchPdf = (ids) =>
  api
    .post("/export/pdf/batch", { tender_ids: ids }, { responseType: "blob" })
    .then((r) => {
      const url = window.URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `gojep_batch_${Date.now()}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    });

export default api;
