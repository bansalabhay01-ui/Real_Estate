// Where the LeadOps API runs. Set VITE_API_URL when deploying (for example on Vercel). Without it, the API is
// expected on port 8000 of the machine that serves this page: localhost while developing, or the laptop's
// address when classmates open the site over the same Wi-Fi (README, "Collecting real test sessions").
const SAME_MACHINE_API = `${window.location.protocol}//${window.location.hostname}:8000`;
export const API_URL = (import.meta.env.VITE_API_URL || SAME_MACHINE_API).replace(/\/+$/, "");
export const WS_URL = API_URL.replace(/^http/, "ws");
