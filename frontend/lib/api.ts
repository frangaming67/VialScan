import type { ConfigStatus, DemoResponse, Defect, ScanSession } from "./types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(typeof detail === "string" ? detail : "No se pudo completar la solicitud.");
  }
  return payload as T;
}

export const api = {
  config: () => request<ConfigStatus>("/api/config", { cache: "no-store" }),
  demo: () => request<DemoResponse>("/api/demo", { cache: "no-store" }),
  sessions: () => request<ScanSession[]>("/api/sessions", { cache: "no-store" }),
  session: (id: string) => request<ScanSession>(`/api/sessions/${id}`, { cache: "no-store" }),
  createSession: (name: string) => request<ScanSession>("/api/sessions", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
  }),
  upload: (id: string, video: File, gps?: File) => {
    const body = new FormData();
    body.append("video", video);
    if (gps) body.append("gps", gps);
    return request<{ id: string; status: string; message: string }>(`/api/sessions/${id}/upload`, { method: "POST", body });
  },
  uploadImages: (id: string, images: File[], gps?: File) => {
    const body = new FormData();
    images.forEach((image) => body.append("images", image));
    if (gps) body.append("gps", gps);
    return request<{ id: string; status: string; message: string }>(`/api/sessions/${id}/images`, { method: "POST", body });
  },
  analyzeLocalImages: (name: string, images: File[], gps?: File) => {
    const body = new FormData();
    body.append("name", name);
    images.forEach((image) => body.append("images", image));
    if (gps) body.append("gps", gps);
    return request<ScanSession>("/api/local-analysis/images", { method: "POST", body });
  },
  analyzeLocalVideo: (name: string, video: File, gps?: File) => {
    const body = new FormData();
    body.append("name", name);
    body.append("video", video);
    if (gps) body.append("gps", gps);
    return request<ScanSession>("/api/local-analysis/video", { method: "POST", body });
  },
  updateDefect: (id: string, updates: Partial<Pick<Defect, "review_status" | "defect_type" | "severity_estimated" | "latitude" | "longitude">>) =>
    request<Defect>(`/api/defects/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(updates),
    }),
};
