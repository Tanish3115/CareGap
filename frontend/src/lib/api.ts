import { getAuthToken, clearAuthSession } from "./auth";
import { AuthResponse, MedicalDocument, PatientProfile, PatientStats, User } from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearAuthSession();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    let errorDetail = "An unexpected error occurred.";
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || JSON.stringify(errorJson);
    } catch {
      errorDetail = await response.text();
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  auth: {
    login: (credentials: { email: string; password: string }): Promise<AuthResponse> =>
      request<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(credentials),
      }),

    register: (userData: Record<string, any>): Promise<User> =>
      request<User>("/auth/register", {
        method: "POST",
        body: JSON.stringify(userData),
      }),

    me: (): Promise<any> => request<any>("/auth/me"),
  },

  documents: {
    list: (docType?: string): Promise<MedicalDocument[]> => {
      const query = docType ? `?document_type=${docType}` : "";
      return request<MedicalDocument[]>(`/documents${query}`);
    },

    upload: async (formData: FormData): Promise<{ message: string; document: MedicalDocument }> => {
      const token = getAuthToken();
      const headers = new Headers();
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }

      const response = await fetch(`${BASE_URL}/documents/upload`, {
        method: "POST",
        headers,
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(error.detail || "Upload failed");
      }

      return response.json();
    },

    download: async (documentId: string, filename: string): Promise<void> => {
      const token = getAuthToken();
      const headers = new Headers();
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }

      const res = await fetch(`${BASE_URL}/documents/${documentId}/download`, {
        headers,
      });

      if (!res.ok) {
        throw new Error("Failed to download document");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
  },

  patients: {
    getProfile: (): Promise<PatientProfile> => request<PatientProfile>("/patients/me"),
    getStats: (): Promise<PatientStats> => request<PatientStats>("/patients/summary/stats"),
  },
};

