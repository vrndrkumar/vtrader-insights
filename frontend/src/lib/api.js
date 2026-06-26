import axios from "axios";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export const api = axios.create({ baseURL: API_BASE_URL, timeout: 120000 });

// Stock list / search
export const listStocks = (params = {}) => api.get("/stocks", { params }).then(r => r.data);
export const searchStocks = (q, params = {}) => api.get("/stocks", { params: { q, limit: 50, ...params } }).then(r => r.data);
export const getStock   = (code)        => api.get(`/stocks/${code}`).then(r => r.data);

// Meta — sectors and industries for filter dropdowns
export const listSectors    = ()              => api.get("/stocks/meta/sectors").then(r => r.data);
export const listIndustries = (sector = null) => api.get("/stocks/meta/industries", { params: sector ? { sector } : {} }).then(r => r.data);

// Analysis
export const analyzeStock = (code)          => api.post(`/analyze/${code}`).then(r => r.data);
export const analyzeBatch = (symbols = null) => api.post("/analyze/batch", { symbols }).then(r => r.data);
export const getJob       = (jobId)          => api.get(`/jobs/${jobId}`).then(r => r.data);
export const listJobs     = (limit = 5)      => api.get("/jobs", { params: { limit } }).then(r => r.data);

// Dashboard
export const getDashboard          = (topN = 6) => api.get("/dashboard", { params: { top_n: topN } }).then(r => r.data);
export const getSectorSummary      = ()          => api.get("/dashboard/sector-summary").then(r => r.data);
export const refreshMarketOverview = ()          => api.post("/dashboard/refresh-market-overview").then(r => r.data);