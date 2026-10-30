import { AuthResponse, MedicalDocument, PatientProfile, PatientStats, User } from "@/types";

export async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/v1${endpoint}`, { ...options, headers, credentials: "same-origin", cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    const detail = Array.isArray(body.detail)
      ? body.detail.map((e: { msg: string }) => e.msg).join("; ") : body.detail;
    if (response.status === 401 && endpoint !== "/auth/login") throw new Error("Authentication required");
    throw new Error(typeof detail === "string" ? detail : "Request failed. Please try again.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export const api = {
  auth: {
    login: (data: { email: string; password: string }) => request<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) }),
    register: (data: Record<string, unknown>) => request<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),
    me: () => request<User & { patient?: PatientProfile; doctor?: { id: string; verification_status: string } }>("/auth/me"),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
  },
  documents: {
    list: (docType?: string, patientId?: string) => {
      const query = new URLSearchParams();
      if (docType) query.set("document_type", docType);
      if (patientId) query.set("patient_id", patientId);
      return request<MedicalDocument[]>(`/documents?${query}`);
    },
    upload: (data: FormData) => request<{ message: string; document: MedicalDocument }>("/documents/upload", { method: "POST", body: data }),
    download: async (id: string, filename: string) => {
      const response = await fetch(`/api/v1/documents/${id}/download`, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error("Document unavailable or access no longer permitted.");
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = filename; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  },
  patients: {
    getProfile: () => request<PatientProfile>("/patients/me"),
    updateProfile: (data: Record<string, unknown>) => request<PatientProfile>("/patients/me", { method: "PUT", body: JSON.stringify(data) }),
    getStats: () => request<PatientStats>("/patients/summary/stats"),
  },
};
