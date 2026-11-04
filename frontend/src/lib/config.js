// Where the LeadOps API runs. Set VITE_API_URL when deploying (for example on Vercel).
export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");
export const WS_URL = API_URL.replace(/^http/, "ws");
