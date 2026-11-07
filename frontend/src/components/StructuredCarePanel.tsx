"use client";
import { useDetailNavigation } from "@/lib/useDetailNavigation";

import { useLanguage } from "@/components/LanguageProvider";
import { DeleteRecord } from "./DeleteRecord";

import { type FormEvent, useEffect, useId, useState } from "react";
import { api, request } from "@/lib/api";
import type { MedicalDocument } from "@/types";
import { allClinicalResources, resourceForKind } from "@/lib/clinical-resources";

export type HealthRecord = {
  id: string;
  patient_id: string;
  kind: string;
  version: number;
  title: string;
  occurred_on: string;
  data: Record<string, string | number | string[] | null>;
  reason: string;
  provenance: string;
  recorded_by_name: string;
  recorded_at: string;
  sources: { id: string; title: string; file_name: string }[];
  linked_record_stale: boolean;
  external_source?: { id: string; path: string; sha256: string } | null;
};
const labels: Record<string, string> = {
  diagnosis: "Diagnosis",
  allergy: "Allergy / reaction",
  lab: "Lab result",
  appointment: "Appointment",
  referral: "Referral",
  test: "Recommended test",
  medication_order: "Recorded medication order",
  dispensing: "Dispensing record",
  confirmed_use: "Clinician medication-use account",
  intervention: "Staff-reviewed intervention",
};
const clinicianOnly = ["medication_order", "dispensing", "confirmed_use", "intervention"];
type Spec = { key: string; label: string; required?: boolean; options?: string[]; date?: boolean };
const care: Spec[] = [
  { key: "due_on", label: "Care due date", required: true, date: true },
  {
    key: "status",
    label: "Care status",
    options: ["pending", "completed", "missed", "cancelled", "unknown"],
  },
  { key: "outcome", label: "Outcome report (required for completed, missed or cancelled care)" },
  { key: "reschedule_requested_for", label: "Requested rescheduling date (optional)", date: true },
  { key: "reschedule_reason", label: "Rescheduling reason (optional)" },
  {
    key: "reschedule_decision",
    label: "Rescheduling request or decision",
    options: ["", "requested", "approved", "declined"],
  },
  { key: "reschedule_review_note", label: "Clinician rescheduling decision note (optional)" },
];
const medication: Spec[] = [
  { key: "name", label: "Recorded medication name", required: true },
  ...["strength", "dose", "frequency", "route", "instructions"].map((key) => ({
    key,
    label: `Recorded ${key} (optional)`,
  })),
  { key: "start_on", label: "Medication period start (optional)", date: true },
  { key: "end_on", label: "Medication period end (optional)", date: true },
  { key: "terminology_code", label: "Reviewed terminology code (optional)" },
  { key: "terminology_system", label: "Terminology system (required with code)" },
  { key: "terminology_evidence", label: "Mapping evidence reference (required with code)" },
];
const specs: Record<string, Spec[]> = {
  diagnosis: [
    { key: "condition", label: "Recorded condition", required: true },
    { key: "status", label: "Condition status", options: ["unknown", "active", "resolved"] },
  ],
  allergy: [
    { key: "substance", label: "Recorded substance", required: true },
    { key: "reaction", label: "Recorded reaction (optional)" },
    { key: "status", label: "Allergy status", options: ["unknown", "active", "inactive"] },
  ],
  lab: [
    { key: "test_name", label: "Lab test name", required: true },
    { key: "value", label: "Source result text (optional)" },
    { key: "unit", label: "Source unit (optional)" },
    { key: "reference_range", label: "Source reference range (optional)" },
  ],
  appointment: care,
  referral: care,
  test: care,
  medication_order: [
    ...medication,
    { key: "status", label: "Order record status", options: ["unknown", "recorded", "cancelled"] },
  ],
  dispensing: [
    ...medication,
    { key: "status", label: "Dispensing record status", options: ["unknown", "recorded", "cancelled"] },
  ],
  confirmed_use: [
    ...medication,
    { key: "status", label: "Clinician-recorded use", options: ["unknown", "taking", "not_taking"] },
  ],
  intervention: [
    {
      key: "action",
      label: "Reviewed intervention",
      options: [
        "staff_outreach",
        "rescheduling",
        "reminder",
        "transport_referral",
        "financial_referral",
        "instruction_clarification",
      ],
    },
    {
      key: "status",
      label: "Intervention status",
      options: ["proposed", "assigned", "completed", "declined", "cancelled"],
    },
    { key: "assigned_staff", label: "Assigned staff (required when assigned)" },
    { key: "outcome", label: "Intervention outcome (required for terminal status)" },
    { key: "experiment_reference", label: "Evaluation reference (optional)" },
  ],
};
const field = "mt-1 w-full min-w-0 rounded-lg border border-slate-300 bg-white p-2 text-sm";
const button =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50";
const textLabel = (key: string) => key.replaceAll("_", " ");

function Details({ record }: { record: HealthRecord }) {
  const { t } = useLanguage();
  return (
    <div className="space-y-1 break-words text-sm">
      <p>
        {t(labels[record.kind])} · {record.occurred_on} {t("· Version")} {record.version}
      </p>
      <p className="text-slate-500">
        {record.provenance === "patient_reported" ? t("Patient-reported") : t("Clinician-recorded")} {t("by")}{" "}
        {record.recorded_by_name}
      </p>
      {Object.entries(record.data)
        .filter(([key]) => key !== "kind")
        .map(([key, value]) => (
          <p className="whitespace-pre-wrap" key={key}>
            <span className="font-medium capitalize">{t(textLabel(key))}:</span>{" "}
            {value === null || value === ""
              ? t("Not recorded")
              : Array.isArray(value)
                ? value.join(", ") || t("Not reported")
                : String(value)}
          </p>
        ))}
      <p>
        {t("Reason:")} {record.reason}
      </p>
      {record.linked_record_stale && (
        <p className="text-amber-800">
          {t(
            "The linked care event has changed. Review its current version before updating this intervention.",
          )}
        </p>
      )}
    </div>
  );
}

function Editor({
  initial,
  patientId,
  allowedKinds,
  documents,
  busy,
  onSave,
  onCancel,
}: {
  initial: HealthRecord | null;
  patientId: string;
  allowedKinds: string[];
  documents: MedicalDocument[];
  busy: boolean;
  onSave: (body: object) => void;
  onCancel: () => void;
}) {
  const { t } = useLanguage();
  const formId = useId();
  const [kind, setKind] = useState(initial?.kind || allowedKinds[0]);
  const [title, setTitle] = useState(initial?.title || "");
  const [date, setDate] = useState(initial?.occurred_on || new Date().toISOString().slice(0, 10));
  const [values, setValues] = useState<HealthRecord["data"]>(
    initial?.data || {
      kind: allowedKinds[0],
      ...Object.fromEntries(
        specs[allowedKinds[0]].filter((spec) => spec.options).map((spec) => [spec.key, spec.options![0]]),
      ),
    },
  );
  const [reason, setReason] = useState("");
  const [checked, setChecked] = useState(false);
  const [selectedSources, setSelectedSources] = useState(initial?.sources.map((source) => source.id) || []);
  const [sources, setSources] = useState<{ id: string; title: string; file_name: string }[]>(documents);
  const [sourcesDone, setSourcesDone] = useState(documents.length < 100);
  const [targets, setTargets] = useState<HealthRecord[]>([]);
  const [targetsDone, setTargetsDone] = useState(false);
  const [error, setError] = useState("");
  const [fetching, setFetching] = useState(false);
  const sourceChoices = [
    ...new Map([...sources, ...(initial?.sources || [])].map((row) => [row.id, row])).values(),
  ];
  async function more(target: boolean) {
    setFetching(true);
    setError("");
    try {
      if (target) {
        const rows = await request<HealthRecord[]>(
          `/clinical/records?patient_id=${patientId}&care_only=true&limit=100&offset=${targets.length}`,
        );
        setTargets((previous) => [...previous, ...rows]);
        setTargetsDone(rows.length < 100);
      } else {
        const rows = await request<MedicalDocument[]>(
          `/documents?patient_id=${patientId}&limit=100&offset=${sources.length}`,
        );
        setSources((previous) => [...previous, ...rows]);
        setSourcesDone(rows.length < 100);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load sources");
    } finally {
      setFetching(false);
    }
  }
  function changeKind(next: string) {
    setKind(next);
    setValues({
      kind: next,
      ...Object.fromEntries(
        specs[next].filter((spec) => spec.options).map((spec) => [spec.key, spec.options![0]]),
      ),
    });
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    const data = Object.fromEntries(
      Object.entries(values).map(([key, value]) => [key, value === "" ? null : value]),
    );
    onSave({
      title,
      occurred_on: date,
      data,
      reason,
      source_checked: checked,
      source_document_ids: selectedSources,
      ...(initial ? { expected_version: initial.version } : { patient_id: patientId }),
    });
  }
  return (
    <form
      aria-label={t("Clinical record editor")}
      data-detail-target="editing"
      onSubmit={submit}
      className="min-w-0 space-y-3 rounded-xl border p-4"
    >
      <h3 className="font-semibold">{initial ? t("Correct clinical record") : t("Add clinical record")}</h3>
      <p className="text-sm text-slate-600">
        {t(
          "Record source details or the reported account. Leave missing details empty. This does not infer a diagnosis, safe dose or completed care.",
        )}
      </p>
      {error && (
        <p role="alert" className="text-red-700">
          {t(error)}
        </p>
      )}
      <fieldset disabled={busy || fetching} className="space-y-3">
        <label className="block text-sm" htmlFor={`${formId}-kind`}>
          {t("Clinical record type")}
        </label>
        <select
          id={`${formId}-kind`}
          className={field}
          disabled={!!initial}
          value={kind}
          onChange={(event) => changeKind(event.target.value)}
        >
          {Object.entries(labels)
            .filter(([key]) => allowedKinds.includes(key))
            .map(([key, label]) => (
              <option key={key} value={key}>
                {t(label)}
              </option>
            ))}
        </select>
        <label className="block text-sm" htmlFor={`${formId}-title`}>
          {t("Clinical record title")}
        </label>
        <input
          id={`${formId}-title`}
          required
          maxLength={255}
          className={field}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <label className="block text-sm" htmlFor={`${formId}-date`}>
          {t("Record date")}
        </label>
        <input
          id={`${formId}-date`}
          type="date"
          required
          max={new Date().toISOString().slice(0, 10)}
          className={field}
          value={date}
          onChange={(event) => setDate(event.target.value)}
        />
        {specs[kind].map((spec) => (
          <div key={spec.key}>
            <label className="block text-sm" htmlFor={`${formId}-${spec.key}`}>
              {t(spec.label)}
            </label>
            {spec.options ? (
              <select
                id={`${formId}-${spec.key}`}
                className={field}
                value={String(values[spec.key] || spec.options[0])}
                onChange={(event) =>
                  setValues((previous) => ({ ...previous, [spec.key]: event.target.value }))
                }
              >
                {spec.options.map((value) => (
                  <option key={value} value={value}>
                    {t(textLabel(value))}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={`${formId}-${spec.key}`}
                className={field}
                required={spec.required}
                type={spec.date ? "date" : "text"}
                maxLength={["outcome", "instructions"].includes(spec.key) ? 2000 : 500}
                value={String(values[spec.key] || "")}
                onChange={(event) =>
                  setValues((previous) => ({ ...previous, [spec.key]: event.target.value }))
                }
              />
            )}
          </div>
        ))}
        {["appointment", "referral", "test"].includes(kind) && (
          <fieldset className="space-y-2 rounded border p-3">
            <legend>{t("Reported access barriers (optional)")}</legend>
            {["transport", "cost", "language", "instructions", "scheduling", "other", "unknown"].map(
              (barrier) => (
                <label className="flex gap-2 text-sm" key={barrier}>
                  <input
                    type="checkbox"
                    checked={Array.isArray(values.barriers) && values.barriers.includes(barrier)}
                    onChange={(event) =>
                      setValues((previous) => ({
                        ...previous,
                        barriers: event.target.checked
                          ? [...(Array.isArray(previous.barriers) ? previous.barriers : []), barrier]
                          : (Array.isArray(previous.barriers) ? previous.barriers : []).filter(
                              (value) => value !== barrier,
                            ),
                      }))
                    }
                  />
                  {t(barrier)}
                </label>
              ),
            )}
          </fieldset>
        )}
        {kind === "intervention" && (
          <div className="space-y-2">
            <label className="block text-sm" htmlFor={`${formId}-target`}>
              {t("Linked care event")}
            </label>
            <select
              id={`${formId}-target`}
              required
              className={field}
              value={String(values.target_id || "")}
              onChange={(event) => {
                const target = targets.find((row) => row.id === event.target.value);
                setValues((previous) => ({
                  ...previous,
                  target_id: event.target.value,
                  target_version: target?.version || 1,
                }));
              }}
            >
              <option value="">{t("Select a loaded care event")}</option>
              {initial?.data.target_id && !targets.some((row) => row.id === initial.data.target_id) && (
                <option value={String(initial.data.target_id)}>
                  {t("Previously linked event · version")} {initial.data.target_version}
                </option>
              )}
              {targets.map((target) => (
                <option key={target.id} value={target.id}>
                  {target.title} {t("· Version")} {target.version}
                </option>
              ))}
            </select>
            <p className="text-xs">
              {t("Linked version:")} {values.target_version || t("Not selected")}
            </p>
            {!targetsDone && (
              <button type="button" className={button} onClick={() => void more(true)}>
                {t("Load care events for intervention")}
              </button>
            )}
            <button
              type="button"
              className={button}
              disabled={!targets.some((row) => row.id === values.target_id)}
              onClick={() =>
                setValues((previous) => ({
                  ...previous,
                  target_version: targets.find((row) => row.id === previous.target_id)!.version,
                }))
              }
            >
              {t("Use loaded care event version")}
            </button>
          </div>
        )}
        <label className="block text-sm" htmlFor={`${formId}-notes`}>
          {t("Clinical record notes (optional)")}
        </label>
        <textarea
          id={`${formId}-notes`}
          maxLength={2000}
          className={field}
          rows={3}
          value={String(values.notes || "")}
          onChange={(event) => setValues((previous) => ({ ...previous, notes: event.target.value }))}
        />
        <fieldset className="space-y-2 rounded border p-3">
          <legend>{t("Original sources (optional)")}</legend>
          <div className="max-h-40 overflow-y-auto">
            {sourceChoices.map((source) => (
              <label key={source.id} className="flex items-start gap-2 break-words text-sm">
                <input
                  type="checkbox"
                  checked={selectedSources.includes(source.id)}
                  disabled={selectedSources.length >= 50 && !selectedSources.includes(source.id)}
                  onChange={(event) =>
                    setSelectedSources((previous) =>
                      event.target.checked
                        ? [...previous, source.id]
                        : previous.filter((id) => id !== source.id),
                    )
                  }
                />
                {source.title}
              </label>
            ))}
          </div>
          {!sourcesDone && (
            <button type="button" className={button} onClick={() => void more(false)}>
              {t("Load more clinical sources")}
            </button>
          )}
        </fieldset>
        <label className="block text-sm" htmlFor={`${formId}-reason`}>
          {t("Reason for clinical record")}
        </label>
        <input
          id={`${formId}-reason`}
          required
          minLength={5}
          maxLength={500}
          className={field}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
        <label className="flex items-start gap-2 text-sm">
          <input
            required
            type="checkbox"
            checked={checked}
            onChange={(event) => setChecked(event.target.checked)}
          />
          {t("I checked this account, its patient/date association and any linked original sources.")}
        </label>
        <div className="flex flex-wrap gap-2">
          <button type="submit" className={button}>
            {t("Save clinical record")}
          </button>
          <button type="button" className={button} onClick={onCancel}>
            {t("Cancel clinical record")}
          </button>
        </div>
      </fieldset>
    </form>
  );
}

export function StructuredCarePanel({
  patientId,
  clinician = false,
  canWrite = true,
  documents,
  readResources = allClinicalResources,
  writeResources = allClinicalResources,
}: {
  patientId: string;
  clinician?: boolean;
  canWrite?: boolean;
  documents: MedicalDocument[];
  readResources?: string[];
  writeResources?: string[];
}) {
  const { t } = useLanguage();
  const readKinds = Object.keys(labels).filter((kind) => readResources.includes(resourceForKind[kind]));
  const writeKinds = readKinds.filter(
    (kind) =>
      canWrite &&
      writeResources.includes(resourceForKind[kind]) &&
      (clinician || !clinicianOnly.includes(kind)),
  );
  const [records, setRecords] = useState<HealthRecord[]>([]);
  const [active, setActive] = useState<HealthRecord | null>(null);
  const [history, setHistory] = useState<HealthRecord[] | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [kind, setKind] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const detailNavigation = useDetailNavigation({ active: !editing && active, editing, history });
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setActive(null);
    setHistory(null);
    setEditing(false);
    const params = new URLSearchParams({
      patient_id: patientId,
      search: query,
      limit: "20",
      offset: String(offset),
    });
    if (kind) params.set("kind", kind);
    request<HealthRecord[]>(`/clinical/records?${params}`)
      .then((rows) => {
        if (!cancelled) {
          setRecords(rows);
          setError("");
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setRecords([]);
          setError(e.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId, kind, query, offset, refresh]);
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load clinical records");
    } finally {
      setBusy(false);
    }
  }
  function showHistory(start: number) {
    if (active)
      void act(async () => {
        setHistory(
          await request<HealthRecord[]>(`/clinical/records/${active.id}/history?limit=20&offset=${start}`),
        );
        setHistoryOffset(start);
      });
  }
  return (
    <section
      aria-label={t("Structured clinical records")}
      ref={detailNavigation}
      className="min-w-0 space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-lg font-semibold">{t("Clinical records & care events")}</h2>
      <p className="text-sm text-slate-600">
        {t(
          "Track diagnoses, recorded allergies, lab text and care outcomes with sources and history. Patient reports and clinician entries remain distinct. Medication events and staff interventions require clinician write permission.",
        )}
      </p>
      {error && (
        <p role="alert" className="break-words text-red-700">
          {t(error)}
        </p>
      )}
      {message && (
        <p role="status" className="text-emerald-800">
          {t(message)}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={button}
          disabled={busy || loading}
          onClick={() => {
            setRefresh((value) => value + 1);
            setMessage("");
          }}
        >
          {t("Refresh clinical records")}
        </button>
        {writeKinds.length > 0 && (
          <button
            type="button"
            className={button}
            disabled={busy}
            onClick={() => {
              setActive(null);
              setEditing(true);
              setHistory(null);
            }}
          >
            {t("Add clinical record")}
          </button>
        )}
      </div>
      <form
        className="grid gap-3 sm:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          setOffset(0);
          setQuery(search);
        }}
      >
        <label className="text-sm">
          {t("Clinical type filter")}
          <select
            className={field}
            value={kind}
            onChange={(event) => {
              setOffset(0);
              setKind(event.target.value);
            }}
          >
            <option value="">{t("All clinical types")}</option>
            {Object.entries(labels)
              .filter(([key]) => readKinds.includes(key))
              .map(([key, value]) => (
                <option key={key} value={key}>
                  {t(value)}
                </option>
              ))}
          </select>
        </label>
        <label className="text-sm">
          {t("Search clinical titles")}
          <input
            className={field}
            maxLength={100}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <button type="submit" className={`${button} self-end`}>
          {t("Search clinical records")}
        </button>
      </form>
      {loading ? (
        <p>{t("Loading clinical records…")}</p>
      ) : (
        <div className="space-y-2">
          {!records.length && <p>{t("No structured clinical records.")}</p>}
          {records.map((record) => (
            <button
              type="button"
              key={record.id}
              className="block w-full break-words rounded-lg border p-3 text-left text-sm"
              onClick={() => {
                setActive({ ...record });
                setEditing(false);
                setHistory(null);
              }}
            >
              <span className="font-semibold">{record.title}</span>
              <span className="block text-slate-500">
                {t(labels[record.kind])} · {record.occurred_on} ·{" "}
                {record.provenance === "patient_reported" ? t("Patient-reported") : t("Clinician-recorded")}
              </span>
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {offset > 0 && (
          <button
            type="button"
            className={button}
            disabled={busy || loading}
            onClick={() => setOffset((value) => Math.max(0, value - 20))}
          >
            {t("Previous clinical records")}
          </button>
        )}
        {records.length === 20 && (
          <button
            type="button"
            className={button}
            disabled={busy || loading}
            onClick={() => setOffset((value) => value + 20)}
          >
            {t("More clinical records")}
          </button>
        )}
      </div>
      {editing && writeKinds.length > 0 && (
        <Editor
          key={active ? `${active.id}-${active.version}` : "new"}
          initial={active}
          patientId={patientId}
          allowedKinds={writeKinds}
          documents={documents}
          busy={busy}
          onCancel={() => setEditing(false)}
          onSave={(body) =>
            void act(async () => {
              await request(`/clinical/records${active ? `/${active.id}` : ""}`, {
                method: active ? "PUT" : "POST",
                body: JSON.stringify(body),
              });
              setOffset(0);
              setRefresh((value) => value + 1);
              setMessage("Clinical record saved. Earlier versions and original sources were preserved.");
            })
          }
        />
      )}
      {active && !editing && (
        <article
          aria-label={t("Selected clinical record")}
          data-detail-target="active"
          className="space-y-3 rounded-xl border p-4"
        >
          <h3 className="font-semibold">{active.title}</h3>
          {!clinician && (
            <DeleteRecord
              key={`${active.id}-${active.version}`}
              path={`/clinical/records/${active.id}`}
              label="Delete health record"
              version={active.version}
            />
          )}
          <Details record={active} />
          <div className="flex flex-wrap gap-2">
            {active.sources.map((source) => (
              <button
                type="button"
                key={source.id}
                className={button}
                disabled={busy}
                onClick={() => void act(() => api.documents.download(source.id, source.file_name))}
              >
                {t("Download clinical source:")} {source.title}
              </button>
            ))}
            {active.external_source && (
              <button
                type="button"
                className={button}
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    const original = await request<{ original: unknown }>(active.external_source!.path);
                    const url = URL.createObjectURL(
                      new Blob([JSON.stringify(original.original, null, 2)], { type: "application/json" }),
                    );
                    const anchor = document.createElement("a");
                    anchor.href = url;
                    anchor.download = "caregap-original-fhir.json";
                    anchor.click();
                    setTimeout(() => URL.revokeObjectURL(url), 1000);
                  })
                }
              >
                {t("Download original FHIR source")}
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {writeKinds.includes(active.kind) && (
              <button type="button" className={button} disabled={busy} onClick={() => setEditing(true)}>
                {t("Correct clinical record")}
              </button>
            )}
            <button type="button" className={button} disabled={busy} onClick={() => showHistory(0)}>
              {t("Clinical record history")}
            </button>
            <button
              type="button"
              className={button}
              onClick={() => {
                setActive(null);
                setHistory(null);
              }}
            >
              {t("Close clinical record")}
            </button>
          </div>
        </article>
      )}
      {history && (
        <section
          aria-label={t("Clinical revision history")}
          data-detail-target="history"
          className="space-y-3"
        >
          <h3 className="font-semibold">{t("Clinical record history")}</h3>
          {history.map((record) => (
            <article key={record.version} className="rounded border p-3">
              <h4 className="font-medium">{record.title}</h4>
              <Details record={record} />
            </article>
          ))}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={button}
              disabled={busy || historyOffset === 0}
              onClick={() => showHistory(Math.max(0, historyOffset - 20))}
            >
              {t("Previous clinical versions")}
            </button>
            <button
              type="button"
              className={button}
              disabled={busy || history.length < 20}
              onClick={() => showHistory(historyOffset + 20)}
            >
              {t("Older clinical versions")}
            </button>
          </div>
        </section>
      )}
    </section>
  );
}
