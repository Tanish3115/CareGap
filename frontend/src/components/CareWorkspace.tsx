"use client";

import { useLanguage } from "@/components/LanguageProvider";

import { useCallback, useEffect, useId, useState, type FormEvent } from "react";
import { request, api } from "@/lib/api";
import type { User, MedicalDocument, PatientProfile, DocumentType } from "@/types";
import { DocumentCard } from "./DocumentCard";
import { DocumentUploadModal } from "./DocumentUploadModal";
import { formatDate } from "@/lib/utils";
import { ClinicalWorkspace } from "./ClinicalWorkspace";
import { MedicationUsePanel } from "./MedicationUsePanel";
import { StructuredCarePanel } from "./StructuredCarePanel";
import { CareInsightsPanel } from "./CareInsightsPanel";
import { OperationsPanel } from "./OperationsPanel";
import { SummaryAssistancePanel } from "./SummaryAssistancePanel";
import { UnifiedTimeline } from "./UnifiedTimeline";
import {
  allClinicalResources,
  clinicalGroups,
  groupLabel,
  resourceForKind,
  selectClinicalGroup,
} from "@/lib/clinical-resources";

type AccessRequest = {
  id: string;
  doctor_name: string;
  organization: string | null;
  organization_verified?: boolean;
  organization_note?: string;
  purpose: string;
  scope: string;
  duration_hours: number;
  allow_upload: boolean;
  include_clinical_records: boolean;
  allow_clinical_write: boolean;
  clinical_resources: string[];
  granted_clinical_resources: string[] | null;
  status: string;
};
type Grant = {
  id: string;
  doctor_name: string;
  scope: string;
  valid_until: string;
  active: boolean;
  is_revoked: boolean;
  document_ids: string[] | null;
  allow_upload: boolean;
  include_clinical_records: boolean;
  allow_clinical_write: boolean;
  clinical_resources: string[];
};
type Audit = { id: string; action: string; resource_type: string; created_at: string; actor_name?: string };
type Doctor = {
  id: string;
  full_name: string;
  license_number: string;
  specialization: string;
  verification_status: string;
};
type Person = {
  id: string;
  full_name: string;
  upload_types: DocumentType[];
  clinical_read: boolean;
  clinical_write: boolean;
  clinical_read_resources: string[];
  clinical_write_resources: string[];
};
type CurrentUser = User & {
  patient?: { id: string; patient_code: string };
  doctor?: { verification_status: string };
};
const field = "w-full rounded-lg border border-slate-300 bg-white p-2 text-sm";
const button =
  "rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 hover:bg-blue-700";

export function CareWorkspace({ user, section = "sharing" }: { user: CurrentUser; section?: string }) {
  const { t } = useLanguage();
  const formId = useId();
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [patients, setPatients] = useState<Person[]>([]);
  const [documents, setDocuments] = useState<MedicalDocument[]>([]);
  const [selected, setSelected] = useState("");
  const [patientId, setPatientId] = useState("");
  const [purpose, setPurpose] = useState("");
  const [scope, setScope] = useState("all");
  const [hours, setHours] = useState(24);
  const [upload, setUpload] = useState(false);
  const [clinicalRead, setClinicalRead] = useState(false);
  const [clinicalWrite, setClinicalWrite] = useState(false);
  const [clinicalResources, setClinicalResources] = useState<string[]>(allClinicalResources);
  const [clinicalSelections, setClinicalSelections] = useState<Record<string, string[]>>({});
  const [organizations, setOrganizations] = useState<{ id: string; name: string; role: string }[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [evidence, setEvidence] = useState<Record<string, string>>({});
  const [recordSelections, setRecordSelections] = useState<Record<string, string[]>>({});
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  const load = useCallback(async () => {
    if (user.role === "patient") {
      const [r, g, a, docs] = await Promise.all([
        request<AccessRequest[]>("/consent/requests"),
        request<Grant[]>("/consent/grants"),
        request<Audit[]>("/consent/audit"),
        api.documents.list(),
      ]);
      setRequests(r);
      setGrants(g);
      setAudit(a);
      setDocuments(docs);
      setProfile(await api.patients.getProfile());
    } else if (user.role === "doctor" && user.doctor?.verification_status === "verified") {
      const [r, p] = await Promise.all([
        request<AccessRequest[]>("/consent/requests"),
        request<Person[]>("/consent/patients"),
      ]);
      setRequests(r);
      setPatients(p);
      setOrganizations(await request("/organizations/mine"));
    } else if (user.role === "admin") {
      const [d, a] = await Promise.all([
        request<Doctor[]>("/admin/doctors"),
        request<Audit[]>("/admin/audit"),
      ]);
      setDoctors(d);
      setAudit(a);
    }
  }, [user.role, user.doctor?.verification_status]);

  useEffect(() => {
    load()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [load]);

  const act = async (fn: () => Promise<unknown>, success: string) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
      await load();
      setMessage(success);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  };

  const sendRequest = (event: FormEvent) => {
    event.preventDefault();
    void act(
      () =>
        request("/consent/requests", {
          method: "POST",
          body: JSON.stringify({
            patient_id: patientId,
            purpose,
            scope,
            duration_hours: hours,
            allow_upload: upload,
            include_clinical_records: clinicalRead,
            allow_clinical_write: clinicalWrite,
            clinical_resources: clinicalRead ? clinicalResources : null,
            organization_id: organizationId || null,
          }),
        }),
      "Access requested. The patient must approve before records are available.",
    );
  };
  const selectedPatient = patients.find((person) => person.id === selected);
  const reads = selectedPatient?.clinical_read_resources || [];
  const writes = selectedPatient?.clinical_write_resources || [];
  const sectionAllowed =
    section === "documents" ||
    section === "patients" ||
    ((section === "timeline" || section === "care") && reads.length > 0) ||
    (section === "consultations" && (reads.includes("consultations") || reads.includes("follow_ups"))) ||
    (section === "medications" && reads.includes("medications")) ||
    (section === "records" && Object.values(resourceForKind).some((group) => reads.includes(group)));
  const scopeKey = `${selected}-${reads.join(",")}-${writes.join(",")}`;

  if (loading)
    return (
      <p role="status" className="p-6 text-slate-600">
        {t("Loading care workspace…")}
      </p>
    );
  return (
    <section className="space-y-6" aria-label={t("Care workspace")}>
      {error && (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {t(error)}
        </p>
      )}
      {message && (
        <p
          role="status"
          className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"
        >
          {t(message)}
        </p>
      )}

      {user.role === "patient" && (
        <>
          {profile && (
            <div hidden={section !== "profile"}>
              <details open className="rounded-xl border bg-white p-5">
                <summary className="cursor-pointer font-semibold">{t("Edit your health profile")}</summary>
                <form
                  className="mt-4 grid gap-4 md:grid-cols-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void act(
                      () =>
                        api.patients.updateProfile({
                          date_of_birth: profile.date_of_birth || null,
                          gender: profile.gender || null,
                          blood_group: profile.blood_group || null,
                          emergency_contact: profile.emergency_contact || null,
                          address: profile.address || null,
                        }),
                      "Profile updated.",
                    );
                  }}
                >
                  <label className="text-sm">
                    {t("Date of birth")}
                    <input
                      type="date"
                      value={profile.date_of_birth || ""}
                      onChange={(e) => setProfile({ ...profile, date_of_birth: e.target.value })}
                      className={field}
                    />
                  </label>
                  <label className="text-sm">
                    {t("Gender")}
                    <input
                      maxLength={20}
                      value={profile.gender || ""}
                      onChange={(e) => setProfile({ ...profile, gender: e.target.value })}
                      className={field}
                    />
                  </label>
                  <label className="text-sm">
                    {t("Blood group")}
                    <select
                      value={profile.blood_group || ""}
                      onChange={(e) => setProfile({ ...profile, blood_group: e.target.value })}
                      className={field}
                    >
                      <option value="">{t("Not recorded")}</option>
                      {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((g) => (
                        <option key={g}>{g}</option>
                      ))}
                    </select>
                  </label>
                  <label className="text-sm">
                    {t("Emergency contact")}
                    <input
                      maxLength={100}
                      value={profile.emergency_contact || ""}
                      onChange={(e) => setProfile({ ...profile, emergency_contact: e.target.value })}
                      className={field}
                    />
                  </label>
                  <label className="text-sm md:col-span-2">
                    {t("Address")}
                    <textarea
                      maxLength={2000}
                      value={profile.address || ""}
                      onChange={(e) => setProfile({ ...profile, address: e.target.value })}
                      className={field}
                    />
                  </label>
                  <button type="submit" disabled={busy} className={button}>
                    {t("Save profile")}
                  </button>
                </form>
              </details>
            </div>
          )}
          <div hidden={section !== "sharing"} className="rounded-xl border bg-white p-5">
            <h3 className="font-semibold">{t("Your patient ID")}</h3>
            <p className="mt-2 font-mono text-xl font-bold tracking-wider">{user.patient?.patient_code}</p>
            <p className="mt-2 text-xs text-slate-500">
              {t(
                "Share this short ID with your clinician to receive an access request. You still decide whether to approve access.",
              )}
            </p>
          </div>
          <div hidden={section !== "sharing"} className="space-y-3">
            <h3 className="font-semibold">{t("Access requests")}</h3>
            {requests.length === 0 && <p className="text-sm text-slate-500">{t("No access requests.")}</p>}
            {requests.map((r) => (
              <article key={r.id} className="space-y-3 rounded-xl border bg-white p-5">
                <p className="font-semibold">
                  {r.doctor_name} <span className="text-xs text-slate-500">· {r.status}</span>
                </p>
                <p className="text-sm text-slate-600">
                  {t("Organization:")} {r.organization || t("Not recorded")} ·{" "}
                  {r.organization_note || t("Self-reported affiliation")}
                </p>
                <p className="text-sm">
                  {t("Purpose:")} {r.purpose}
                </p>
                <p className="text-sm">
                  {t("Scope:")} {r.scope.replaceAll("_", " ")} · {r.duration_hours} {t("hours ·")}{" "}
                  {r.allow_upload ? t("Read and upload") : t("Read only")}
                </p>
                {r.status === "pending" && (
                  <>
                    {r.include_clinical_records && (
                      <>
                        <p className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
                          {t(
                            "Includes selected clinical groups and their histories. Original documents remain shared under the all-document consent.",
                          )}{" "}
                          {r.allow_clinical_write
                            ? t(
                                "Clinical write permission applies to the approved groups; changes keep their author and history. Only the patient can change their medication-use reports.",
                              )
                            : t("Approved clinical groups are shared for viewing only.")}
                        </p>
                        <fieldset className="space-y-2 rounded border p-3">
                          <legend className="font-medium">{t("Clinical groups to approve")}</legend>
                          <p className="text-xs text-slate-600">
                            {t(
                              "You may remove requested groups. Interventions include linked care plans. Prescription draft access also needs document transcription reviews.",
                            )}
                          </p>
                          {(r.clinical_resources || allClinicalResources).map((group) => (
                            <label key={group} className="flex items-start gap-2 text-sm">
                              <input
                                type="checkbox"
                                checked={(
                                  clinicalSelections[r.id] ||
                                  r.clinical_resources ||
                                  allClinicalResources
                                ).includes(group)}
                                onChange={(event) =>
                                  setClinicalSelections((previous) => ({
                                    ...previous,
                                    [r.id]: selectClinicalGroup(
                                      previous[r.id] || r.clinical_resources || allClinicalResources,
                                      group,
                                      event.target.checked,
                                    ),
                                  }))
                                }
                              />
                              {t(groupLabel(group))}
                            </label>
                          ))}
                        </fieldset>
                      </>
                    )}
                    {!r.allow_upload && !r.include_clinical_records && (
                      <fieldset className="space-y-2 text-sm">
                        <legend className="font-medium">
                          {t(
                            "Optionally restrict to selected records (leave unchecked to share this document category)",
                          )}
                        </legend>
                        {documents
                          .filter(
                            (d) =>
                              r.scope === "all" ||
                              d.document_type === (r.scope === "labs_only" ? "lab_report" : "prescription"),
                          )
                          .map((d) => (
                            <label key={d.id} className="flex gap-2">
                              <input
                                type="checkbox"
                                checked={(recordSelections[r.id] || []).includes(d.id)}
                                onChange={(e) =>
                                  setRecordSelections((prev) => ({
                                    ...prev,
                                    [r.id]: e.target.checked
                                      ? [...(prev[r.id] || []), d.id]
                                      : (prev[r.id] || []).filter((id) => id !== d.id),
                                  }))
                                }
                              />
                              {d.title}
                            </label>
                          ))}
                      </fieldset>
                    )}
                    <div className="flex gap-3">
                      <button
                        type="button"
                        disabled={
                          busy ||
                          (r.include_clinical_records &&
                            (clinicalSelections[r.id] || r.clinical_resources || allClinicalResources)
                              .length === 0)
                        }
                        className={button}
                        onClick={() =>
                          void act(
                            () =>
                              request(`/consent/requests/${r.id}/decision`, {
                                method: "POST",
                                body: JSON.stringify({
                                  decision: "approve",
                                  document_ids: recordSelections[r.id]?.length
                                    ? recordSelections[r.id]
                                    : null,
                                  clinical_resources: r.include_clinical_records
                                    ? clinicalSelections[r.id] || r.clinical_resources || allClinicalResources
                                    : null,
                                }),
                              }),
                            "Access approved.",
                          )
                        }
                      >
                        {t("Approve")}
                      </button>
                      <button
                        type="button"
                        disabled={busy}
                        className="rounded-lg border px-4 py-2 text-sm"
                        onClick={() =>
                          void act(
                            () =>
                              request(`/consent/requests/${r.id}/decision`, {
                                method: "POST",
                                body: JSON.stringify({ decision: "deny" }),
                              }),
                            "Access denied.",
                          )
                        }
                      >
                        {t("Deny")}
                      </button>
                    </div>
                  </>
                )}
              </article>
            ))}
          </div>
          <div hidden={section !== "sharing"} className="space-y-3">
            <h3 className="font-semibold">{t("Consent grants")}</h3>
            {!grants.length && <p className="text-sm text-slate-500">{t("No consent grants.")}</p>}
            {grants.map((g) => (
              <article
                key={g.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white p-5"
              >
                <div>
                  <p className="font-semibold">{g.doctor_name}</p>
                  <p className="text-sm text-slate-600">
                    {g.scope.replaceAll("_", " ")} ·{" "}
                    {g.document_ids
                      ? t("{value0} selected records", { value0: g.document_ids.length })
                      : t("Category access")}{" "}
                    · {g.active ? t("Active") : g.is_revoked ? t("Revoked") : t("Expired")} {t("· Expires")}{" "}
                    {new Date(g.valid_until + (g.valid_until.endsWith("Z") ? "" : "Z")).toLocaleString()}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    {t("Documents:")} {g.allow_upload ? t("read and upload") : t("read only")}
                    {t(". Clinical records and history:")}{" "}
                    {g.include_clinical_records
                      ? g.allow_clinical_write
                        ? t("read, create and correct")
                        : t("read only")
                      : t("not shared")}
                    .
                  </p>
                  {g.include_clinical_records && (
                    <p className="mt-1 text-sm">
                      {t("Approved groups:")}{" "}
                      {g.clinical_resources.map((group) => t(groupLabel(group))).join(", ")}
                    </p>
                  )}
                </div>
                {g.active && (
                  <button
                    type="button"
                    className="rounded-lg border border-red-200 px-4 py-2 text-sm text-red-700"
                    disabled={busy}
                    onClick={() =>
                      void act(
                        () => request(`/consent/grants/${g.id}/revoke`, { method: "POST" }),
                        "Future access has been revoked.",
                      )
                    }
                  >
                    {t("Revoke")}
                  </button>
                )}
              </article>
            ))}
          </div>
        </>
      )}

      {user.role === "doctor" &&
        (user.doctor?.verification_status !== "verified" ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-6">
            <h3 className="font-semibold">{t("Professional verification required")}</h3>
            <p className="mt-2 text-sm">
              {t("Current status:")} {user.doctor?.verification_status || t("pending")}
              {t(
                ". An administrator must review your professional evidence before you can request or access patient information.",
              )}
            </p>
          </div>
        ) : (
          <>
            <form
              hidden={section !== "patients"}
              className="grid gap-4 rounded-xl border bg-white p-5 md:grid-cols-2"
              onSubmit={sendRequest}
            >
              <h3 className="font-semibold md:col-span-2">{t("Request patient access")}</h3>
              <label className="space-y-1 text-sm">
                {t("Patient ID")}
                <input
                  required
                  minLength={4}
                  maxLength={4}
                  pattern="[A-Za-z][0-9]{3}"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder={t("e.g. A123")}
                  aria-label={t("Patient ID")}
                  aria-describedby="patient-id-help"
                  value={patientId}
                  onChange={(e) => setPatientId(e.target.value.toUpperCase())}
                  className={field}
                />
                <span id="patient-id-help" className="block text-xs text-slate-500">
                  {t(
                    "Example: A123 — one letter followed by three digits. Find this ID on the patient's dashboard.",
                  )}
                </span>
              </label>
              <label className="space-y-1 text-sm">
                {t("Purpose")}
                <input
                  required
                  minLength={5}
                  maxLength={255}
                  value={purpose}
                  onChange={(e) => setPurpose(e.target.value)}
                  className={field}
                />
              </label>
              <div className="space-y-1 text-sm">
                <label htmlFor={`${formId}-organization`}>{t("Representing organization")}</label>
                <select
                  id={`${formId}-organization`}
                  className={field}
                  value={organizationId}
                  onChange={(event) => setOrganizationId(event.target.value)}
                >
                  <option value="">{t("Personal capacity / self-reported affiliation")}</option>
                  {organizations
                    .filter((org) => org.role === "clinician")
                    .map((org) => (
                      <option value={org.id} key={org.id}>
                        {org.name} {t("· verified membership")}
                      </option>
                    ))}
                </select>
              </div>
              <label className="space-y-1 text-sm">
                {t("Record scope")}
                <select
                  value={scope}
                  onChange={(e) => {
                    setScope(e.target.value);
                    if (e.target.value !== "all") {
                      setClinicalRead(false);
                      setClinicalWrite(false);
                    }
                  }}
                  className={field}
                >
                  <option value="all">{t("All document categories")}</option>
                  <option value="prescriptions_only">{t("Prescriptions")}</option>
                  <option value="labs_only">{t("Lab reports")}</option>
                </select>
              </label>
              <label className="space-y-1 text-sm">
                {t("Duration in hours")}
                <input
                  required
                  type="number"
                  min={1}
                  max={720}
                  value={hours}
                  onChange={(e) => setHours(Number(e.target.value))}
                  className={field}
                />
              </label>
              <label className="flex gap-2 text-sm">
                <input type="checkbox" checked={upload} onChange={(e) => setUpload(e.target.checked)} />
                {t("Also request permission to upload documents")}
              </label>
              <fieldset className="space-y-3 rounded-lg border p-3 text-sm md:col-span-2">
                <legend className="px-1 font-medium">{t("Clinical records (optional)")}</legend>
                <label className="flex gap-2">
                  <input
                    type="checkbox"
                    disabled={scope !== "all"}
                    checked={clinicalRead}
                    onChange={(e) => {
                      setClinicalRead(e.target.checked);
                      if (!e.target.checked) setClinicalWrite(false);
                    }}
                  />
                  {t("Request clinical records viewing access")}
                </label>
                <label className="flex gap-2">
                  <input
                    type="checkbox"
                    disabled={!clinicalRead}
                    checked={clinicalWrite}
                    onChange={(e) => setClinicalWrite(e.target.checked)}
                  />
                  {t("Also request permission to create and correct clinical records")}
                </label>
                <p className="text-xs text-slate-500">
                  {t(
                    "Select the clinical groups to share, including their histories. Write permission allows clinician reconciliation; patient accounts remain patient-owned. Requires all document categories. The patient must explicitly approve these permissions.",
                  )}
                </p>
              </fieldset>
              {clinicalRead && (
                <fieldset className="space-y-2 rounded border p-3 md:col-span-2">
                  <legend className="font-medium">{t("Requested clinical groups")}</legend>
                  <p className="text-xs text-slate-600">
                    {t(
                      "Original documents remain shared under the all-document grant. These choices limit added clinical records and histories. Interventions need care plans; prescription drafts need medications and document transcription reviews.",
                    )}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="text-sm text-blue-700 underline"
                      onClick={() => setClinicalResources(allClinicalResources)}
                    >
                      {t("Select all clinical groups")}
                    </button>
                    <button
                      type="button"
                      className="text-sm text-blue-700 underline"
                      onClick={() => setClinicalResources([])}
                    >
                      {t("Clear clinical groups")}
                    </button>
                  </div>
                  {Object.entries(clinicalGroups).map(([group, label]) => (
                    <label key={group} className="flex items-start gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={clinicalResources.includes(group)}
                        onChange={(event) =>
                          setClinicalResources((previous) =>
                            selectClinicalGroup(previous, group, event.target.checked),
                          )
                        }
                      />
                      {t(label)}
                    </label>
                  ))}
                </fieldset>
              )}
              <button
                type="submit"
                disabled={busy || (clinicalRead && !clinicalResources.length)}
                className={button}
              >
                {t("Send access request")}
              </button>
            </form>
            <div className="rounded-xl border bg-white p-5">
              <h3 className="mb-3 font-semibold">{t("Authorized patients")}</h3>
              <label className="text-sm">
                {t("Select a patient")}
                <select
                  className={field}
                  value={selected}
                  onChange={(e) => {
                    const id = e.target.value;
                    setSelected(id);
                    setDocuments([]);
                    if (id)
                      void act(
                        async () => setDocuments(await api.documents.list(undefined, id)),
                        "Authorized records loaded.",
                      );
                  }}
                >
                  <option value="">{t("Select patient")}</option>
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.full_name}
                    </option>
                  ))}
                </select>
              </label>
              {!patients.length && (
                <p className="mt-3 text-sm text-slate-500">{t("No active patient grants.")}</p>
              )}
            </div>
            {!selected && section !== "patients" && (
              <p
                role="status"
                className="rounded-xl border border-blue-100 bg-blue-50 p-5 text-sm text-blue-900"
              >
                {t("Select a patient to view authorized records.")}
              </p>
            )}
            {selected && !sectionAllowed && (
              <p
                role="status"
                className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900"
              >
                {t("This feature is outside the patient's approved sharing scope.")}
              </p>
            )}
            {selected && (
              <div hidden={section !== "documents"} className="grid gap-4 md:grid-cols-2">
                {documents.map((d) => (
                  <DocumentCard key={d.id} document={d} />
                ))}
                {!documents.length && (
                  <p className="text-sm text-slate-500">
                    {t("No documents available within the approved scope.")}
                  </p>
                )}
              </div>
            )}
            {selected && reads.length > 0 && (
              <div hidden={section !== "timeline"}>
                <UnifiedTimeline key={`timeline-${scopeKey}`} patientId={selected} readResources={reads} />
              </div>
            )}
            {selected && (reads.includes("consultations") || reads.includes("follow_ups")) && (
              <div hidden={section !== "consultations"}>
                <ClinicalWorkspace
                  key={scopeKey}
                  patientId={selected}
                  canWrite={writes.length > 0}
                  readResources={reads}
                  writeResources={writes}
                  documents={documents}
                />
              </div>
            )}
            {selected && reads.includes("medications") && (
              <div hidden={section !== "medications"}>
                <MedicationUsePanel
                  key={`medication-${scopeKey}`}
                  patientId={selected}
                  canReview={writes.includes("medications")}
                />
              </div>
            )}
            {selected && Object.values(resourceForKind).some((group) => reads.includes(group)) && (
              <div hidden={section !== "records"}>
                <StructuredCarePanel
                  key={`clinical-${scopeKey}`}
                  patientId={selected}
                  clinician
                  canWrite={writes.length > 0}
                  readResources={reads}
                  writeResources={writes}
                  documents={documents}
                />
              </div>
            )}
            {selected && reads.length > 0 && (
              <div hidden={section !== "care"}>
                <SummaryAssistancePanel key={`summary-${scopeKey}`} patientId={selected} />
              </div>
            )}
            {selected && reads.length > 0 && (
              <div hidden={section !== "care"}>
                <CareInsightsPanel
                  key={`insights-${scopeKey}`}
                  patientId={selected}
                  canWrite={writes.length > 0}
                  readResources={reads}
                  writeResources={writes}
                />
              </div>
            )}
            {selected && !!patients.find((p) => p.id === selected)?.upload_types.length && (
              <>
                <button
                  hidden={section !== "documents"}
                  type="button"
                  className={button}
                  onClick={() => setUploadOpen(true)}
                >
                  {t("Upload for selected patient")}
                </button>
                <DocumentUploadModal
                  isOpen={uploadOpen}
                  onClose={() => setUploadOpen(false)}
                  patientId={selected}
                  allowedTypes={patients.find((p) => p.id === selected)?.upload_types}
                  onUploadSuccess={(doc) => setDocuments((prev) => [doc, ...prev])}
                />
              </>
            )}
            <div hidden={section !== "patients"} className="rounded-xl border bg-white p-5">
              <h3 className="font-semibold">{t("Your requests")}</h3>
              {!requests.length && (
                <p className="mt-2 text-sm text-slate-500">{t("No requests submitted.")}</p>
              )}
              {requests.map((r) => (
                <p className="mt-3 text-sm" key={r.id}>
                  {r.purpose} · {r.scope.replaceAll("_", " ")} · {r.status}
                  {r.include_clinical_records && (
                    <span className="block">
                      {r.granted_clinical_resources ? t("Approved groups: ") : t("Requested groups: ")}
                      {(r.granted_clinical_resources || r.clinical_resources)
                        .map((group) => t(groupLabel(group)))
                        .join(", ")}
                    </span>
                  )}
                </p>
              ))}
            </div>
          </>
        ))}

      {user.role === "admin" && (
        <div hidden={section !== "verification"} className="space-y-3">
          <h3 className="font-semibold">{t("Professional verification queue")}</h3>
          {!doctors.length && <p className="text-sm text-slate-500">{t("No doctors registered.")}</p>}
          {doctors.map((d) => (
            <article className="space-y-3 rounded-xl border bg-white p-5" key={d.id}>
              <p className="font-semibold">
                {d.full_name} · {d.verification_status}
              </p>
              <p className="text-sm">
                {d.license_number} · {d.specialization}
              </p>
              <label className="block text-sm">
                {t("Evidence reference")}
                <input
                  minLength={5}
                  maxLength={500}
                  value={evidence[d.id] || ""}
                  onChange={(e) => setEvidence((prev) => ({ ...prev, [d.id]: e.target.value }))}
                  placeholder={t("Reference to reviewed professional verification evidence")}
                  className={field}
                />
              </label>
              <div className="flex gap-3">
                {["verified", "rejected", "pending"].map((status) => (
                  <button
                    type="button"
                    key={status}
                    disabled={busy || (evidence[d.id] || "").length < 5}
                    className={button}
                    onClick={() =>
                      void act(
                        () =>
                          request(`/admin/doctors/${d.id}/verification`, {
                            method: "POST",
                            body: JSON.stringify({ status, evidence_reference: evidence[d.id] }),
                          }),
                        "Verification decision recorded.",
                      )
                    }
                  >
                    {status === "verified"
                      ? t("Verify")
                      : status === "rejected"
                        ? t("Reject")
                        : t("Reset to pending")}
                  </button>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}

      {user.role === "admin" && (
        <div hidden={section !== "operations"}>
          <OperationsPanel />
        </div>
      )}
      {(user.role === "patient" || user.role === "admin") && (
        <div
          hidden={section !== (user.role === "patient" ? "sharing" : "audit")}
          className="overflow-x-auto rounded-xl border bg-white p-5"
        >
          <h3 className="mb-3 font-semibold">
            {user.role === "patient" ? t("Record access history") : t("Operational audit events")}
          </h3>
          {!audit.length ? (
            <p className="text-sm text-slate-500">{t("No events recorded.")}</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-slate-500">
                  <th className="py-2">{t("Date")}</th>
                  <th>{t("Action")}</th>
                  {user.role === "patient" && <th>{t("Actor")}</th>}
                  <th>{t("Resource")}</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((e) => (
                  <tr key={e.id} className="border-b last:border-0">
                    <td className="py-2">{formatDate(e.created_at)}</td>
                    <td>{e.action.replaceAll("_", " ")}</td>
                    {user.role === "patient" && <td>{e.actor_name || t("System")}</td>}
                    <td>{e.resource_type.replaceAll("_", " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}
