import { AuthResponse } from "@/types";

// The credential is an HttpOnly server cookie. Never persist tokens in browser storage.
export function setAuthSession(_data: AuthResponse) {
  if (typeof window !== "undefined") {
    localStorage.removeItem("caregap_access_token");
    localStorage.removeItem("caregap_user");
  }
}

export function clearAuthSession() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("caregap_access_token");
    localStorage.removeItem("caregap_user");
  }
}
