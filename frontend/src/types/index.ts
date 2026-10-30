export type UserRole = "patient" | "doctor" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  phone?: string;
  is_active: boolean;
}

export interface PatientProfile {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  phone?: string;
  date_of_birth?: string;
  gender?: string;
  blood_group?: string;
  emergency_contact?: string;
  address?: string;
  abha_id?: string;
  created_at: string;
}

export type DocumentType =
  | "prescription"
  | "lab_report"
  | "discharge_summary"
  | "referral"
  | "scan"
  | "other";

export interface MedicalDocument {
  id: string;
  patient_id: string;
  uploader_id: string;
  title: string;
  document_type: DocumentType;
  file_name: string;
  file_size: number;
  mime_type: string;
  sha256_hash: string;
  status: "uploaded" | "processing" | "extracted" | "verified";
  clinical_date?: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
  user_id: string;
  full_name: string;
  email: string;
}

export interface PatientStats {
  total_documents: number;
  prescriptions_count: number;
  lab_reports_count: number;
  pending_care_gaps: number;
  active_doctor_grants: number;
}

