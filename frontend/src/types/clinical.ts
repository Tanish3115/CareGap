export type Provenance = "patient_reported" | "clinician_recorded";
export type TaskStatus = "pending" | "completed" | "cancelled";
export type ClinicalSource = { id: string; title: string; file_name: string };

export interface Encounter {
  id: string;
  patient_id: string;
  created_by: string;
  version: number;
  occurred_on: string;
  title: string;
  notes: string;
  sources: ClinicalSource[];
  recorded_by: string;
  recorded_by_name: string;
  provenance: Provenance;
  correction_reason: string;
  recorded_at: string;
  created_at: string;
}

export interface FollowUp {
  id: string;
  patient_id: string;
  encounter_id: string;
  created_by: string;
  version: number;
  title: string;
  due_on: string;
  status: TaskStatus;
  outcome: string | null;
  overdue: boolean;
  recorded_by: string;
  recorded_by_name: string;
  provenance: Provenance;
  correction_reason: string;
  recorded_at: string;
  created_at: string;
}

export interface TimelineEntry {
  id: string;
  kind: "document" | "encounter";
  event_date: string;
  date_basis: "clinical_date" | "upload_date" | "consultation_date";
  title: string;
  provenance: Provenance | "source_unverified";
}

export type EncounterInput = {
  occurred_on: string; title: string; notes: string; source_document_ids: string[];
  expected_version?: number; correction_reason?: string;
};
export type FollowUpInput = {
  title: string; due_on: string; status: TaskStatus; outcome: string | null;
  expected_version?: number; correction_reason?: string;
};
