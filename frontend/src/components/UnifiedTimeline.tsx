"use client";
import { useDetailNavigation } from "@/lib/useDetailNavigation";

import { useLanguage } from "@/components/LanguageProvider";

import { useEffect, useId, useRef, useState } from "react";
import { api, request } from "@/lib/api";
import { allClinicalResources, resourceForKind } from "@/lib/clinical-resources";

type Entry = {
  id: string;
  kind: string;
  title: string;
  event_date: string;
  date_basis: string;
  provenance: string;
  version: number | null;
  source_path: string;
  history_path: string | null;
  document_id: string | null;
  file_name: string | null;
};
const labels: Record<string, string> = {
  document: "Original document",
  encounter: "Consultation",
  follow_up: "Consultation follow-up",
  reported_medication_use: "Patient medication account",
  historical_prescription: "Historical prescription",
  transcription_review: "Transcription review",
  diagnosis: "Diagnosis",
  allergy: "Allergy / reaction",
  lab: "Lab result",
  appointment: "Appointment plan",
  referral: "Referral plan",
  test: "Recommended test",
  medication_order: "Recorded medication order",
  dispensing: "Dispensing record",
  confirmed_use: "Clinician medication-use account",
  intervention: "Staff intervention",
};
const groups: Record<string, string> = {
  ...resourceForKind,
  encounter: "consultations",
  follow_up: "follow_ups",
  reported_medication_use: "medications",
  historical_prescription: "medications",
  transcription_review: "source_reviews",
};
const button = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50";
const field = "mt-1 w-full min-w-0 rounded-lg border border-slate-300 bg-white p-2 text-sm";

const sourceFields = [
  "version",
  "prescription_version",
  "title",
  "name",
  "document_type",
  "clinical_date",
  "occurred_on",
  "reported_on",
  "due_on",
  "condition",
  "substance",
  "reaction",
  "test_name",
  "value",
  "unit",
  "reference_range",
  "strength",
  "dose",
  "frequency",
  "route",
  "duration",
  "instructions",
  "use_status",
  "status",
  "notes",
  "reviewed_text",
  "outcome",
  "barriers",
  "reschedule_requested_for",
  "reschedule_reason",
  "reschedule_decision",
  "reschedule_review_note",
  "action",
  "assigned_staff",
  "reason",
  "correction_reason",
  "recorded_by_name",
  "author_name",
  "confirmed_by_name",
  "created_at",
];
function sourceValue(value: unknown): string {
  if (value === null || value === "" || value === undefined) return "Not recorded";
  if (Array.isArray(value)) return value.map(sourceValue).join(", ") || "Not recorded";
  if (typeof value === "object") {
    const item = value as Record<string, unknown>;
    return "value" in item ? sourceValue(item.value) : JSON.stringify(item);
  }
  return String(value);
}
function SourceRecord({ value }: { value: unknown }) {
  const { t } = useLanguage();
  if (!value || typeof value !== "object") return <p>{t("No source details recorded.")}</p>;
  const root = value as Record<string, unknown>;
  const values = {
    ...root,
    ...(root.data && typeof root.data === "object" ? (root.data as Record<string, unknown>) : {}),
  };
  return (
    <div className="space-y-2 break-words text-sm">
      {(root.source_stale || root.review_stale) === true && (
        <p className="text-amber-900">
          {t(
            "The source or account changed after review. Review the current versions before relying on this entry.",
          )}
        </p>
      )}
      {sourceFields
        .filter((key) => key in values)
        .map((key) => (
          <p key={key} className="whitespace-pre-wrap">
            <span className="font-medium capitalize">{t(key.replaceAll("_", " "))}:</span>{" "}
            {sourceValue(values[key])}
          </p>
        ))}
      {Array.isArray(root.items) &&
        root.items.map((item, index) => (
          <div className="rounded border p-3" key={index}>
            <SourceRecord value={item} />
          </div>
        ))}
    </div>
  );
}

export function SourceData({ value, entryId }: { value: unknown; entryId?: string }) {
  const { t } = useLanguage();
  const values = Array.isArray(value) ? value : [value];
  const selected =
    entryId && values.some((item) => item?.id === entryId)
      ? values.filter((item) => item?.id === entryId)
      : values;
  return (
    <div className="space-y-3">
      {selected.map((item, index) => (
        <SourceRecord key={index} value={item} />
      ))}
      <details>
        <summary className="cursor-pointer text-sm">{t("Source record data")}</summary>
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">
          {JSON.stringify(selected, null, 2)}
        </pre>
      </details>
    </div>
  );
}

export function UnifiedTimeline({
  patientId,
  readResources = allClinicalResources,
}: {
  patientId: string;
  readResources?: string[];
}) {
  const { t } = useLanguage();
  const id = useId();
  const sourceButtons = useRef(new Map<string, HTMLButtonElement>());
  const [entries, setEntries] = useState<Entry[]>([]);
  const [kind, setKind] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [fromDraft, setFromDraft] = useState("");
  const [toDraft, setToDraft] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [active, setActive] = useState<Entry | null>(null);
  const [detail, setDetail] = useState<unknown>(null);
  const [history, setHistory] = useState<unknown>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [historyCount, setHistoryCount] = useState(0);
  const detailNavigation = useDetailNavigation({ detail, history });
  const scopeKey = [...readResources].sort().join(",");
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setActive(null);
    setDetail(null);
    setHistory(null);
    const params = new URLSearchParams({
      patient_id: patientId,
      search,
      limit: "20",
      offset: String(offset),
    });
    if (kind) params.set("kind", kind);
    if (from) params.set("date_from", from);
    if (to) params.set("date_to", to);
    request<Entry[]>(`/clinical/unified-timeline?${params}`)
      .then((rows) => {
        if (!cancelled) {
          setEntries(rows);
          setError("");
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setEntries([]);
          setError(e.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId, scopeKey, kind, search, from, to, offset, refresh]);
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setActive(null);
      setDetail(null);
      setHistory(null);
      setError(e instanceof Error ? e.message : "Unable to load timeline source");
    } finally {
      setBusy(false);
    }
  }
  function showHistory(start: number) {
    if (active?.history_path)
      void act(async () => {
        const rows = await request<unknown[]>(`${active.history_path}?limit=20&offset=${start}`);
        setHistory(rows);
        setHistoryCount(rows.length);
        setHistoryOffset(start);
      });
  }
  return (
    <section
      aria-label={t("Unified medical timeline")}
      ref={detailNavigation}
      className="min-w-0 space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-lg font-semibold">{t("Unified medical timeline")}</h2>
      <p className="text-sm text-slate-600">
        {t(
          "Current authorized documents, consultations, clinical records, care plans and medication accounts in date order. Due dates describe plans; a prescription does not establish current use. Clinical group restrictions apply to every source and history request.",
        )}
      </p>
      {error && (
        <p role="alert" className="break-words text-red-700">
          {t(error)}
        </p>
      )}
      <button
        type="button"
        className={button}
        disabled={busy || loading}
        onClick={() => setRefresh((value) => value + 1)}
      >
        {t("Refresh unified timeline")}
      </button>
      <form
        className="grid min-w-0 gap-3 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          setOffset(0);
          setSearch(searchDraft);
          setFrom(fromDraft);
          setTo(toDraft);
        }}
      >
        <div>
          <label className="block text-sm" htmlFor={`${id}-kind`}>
            {t("Unified timeline type")}
          </label>
          <select
            className={field}
            id={`${id}-kind`}
            value={kind}
            onChange={(event) => {
              setOffset(0);
              setKind(event.target.value);
            }}
          >
            <option value="">{t("All shared types")}</option>
            {Object.entries(labels)
              .filter(([key]) => key === "document" || readResources.includes(groups[key]))
              .map(([key, label]) => (
                <option value={key} key={key}>
                  {t(label)}
                </option>
              ))}
          </select>
        </div>
        <label className="block text-sm">
          {t("Search unified timeline")}
          <input
            className={field}
            maxLength={100}
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
          />
        </label>
        <label className="block text-sm">
          {t("Timeline from date")}
          <input
            className={field}
            type="date"
            value={fromDraft}
            onChange={(event) => setFromDraft(event.target.value)}
          />
        </label>
        <label className="block text-sm">
          {t("Timeline through date")}
          <input
            className={field}
            type="date"
            value={toDraft}
            onChange={(event) => setToDraft(event.target.value)}
          />
        </label>
        <button type="submit" className={button}>
          {t("Apply timeline filters")}
        </button>
      </form>
      {loading ? (
        <p>{t("Loading unified timeline…")}</p>
      ) : (
        <div className="space-y-2">
          {!entries.length && <p>{t("No authorized entries match these filters.")}</p>}
          {entries.map((entry) => (
            <button
              type="button"
              key={`${entry.kind}-${entry.id}`}
              ref={(element) => {
                const key = `${entry.kind}-${entry.id}`;
                if (element) sourceButtons.current.set(key, element);
                else sourceButtons.current.delete(key);
              }}
              aria-expanded={active?.id === entry.id && active?.kind === entry.kind}
              aria-controls={
                active?.id === entry.id && active?.kind === entry.kind ? `${id}-source` : undefined
              }
              className={`timeline-event block w-full break-words rounded-lg border p-4 text-left text-sm ${active?.id === entry.id && active?.kind === entry.kind ? "border-blue-300 bg-blue-50" : "bg-white"}`}
              disabled={busy}
              onClick={() =>
                void act(async () => {
                  const value = await request(entry.source_path);
                  setActive(entry);
                  setDetail(value);
                  setHistory(null);
                })
              }
            >
              <span className="font-semibold">{entry.title}</span>
              <span className="block">
                {t(labels[entry.kind])} · {entry.event_date} · {t(entry.date_basis.replaceAll("_", " "))}
              </span>
              <span className="block text-xs text-slate-500">
                {t(entry.provenance.replaceAll("_", " "))}
                {entry.version ? t(" · Version {value0}", { value0: entry.version }) : ""}
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
            {t("Previous unified entries")}
          </button>
        )}
        {entries.length === 20 && (
          <button
            type="button"
            className={button}
            disabled={busy || loading}
            onClick={() => setOffset((value) => value + 20)}
          >
            {t("More unified entries")}
          </button>
        )}
      </div>
      {active && detail !== null && (
        <article
          id={`${id}-source`}
          aria-label={t("Unified timeline source")}
          data-detail-target="detail"
          className="min-w-0 space-y-3 break-words rounded-xl border p-4"
        >
          <h3 className="font-semibold">{active.title}</h3>
          <p className="text-sm">
            {t(labels[active.kind])} · {active.event_date} · {t(active.date_basis.replaceAll("_", " "))}
          </p>
          <SourceData value={detail} entryId={active.id} />
          <div className="flex flex-wrap gap-2">
            {active.document_id && active.file_name && (
              <button
                type="button"
                className={button}
                disabled={busy}
                onClick={() => void act(() => api.documents.download(active.document_id!, active.file_name!))}
              >
                {t("Download timeline original")}
              </button>
            )}
            {active.history_path && (
              <button type="button" className={button} disabled={busy} onClick={() => showHistory(0)}>
                {t("View timeline source history")}
              </button>
            )}
            <button
              type="button"
              className={button}
              onClick={() => {
                sourceButtons.current.get(`${active.kind}-${active.id}`)?.focus();
                setActive(null);
                setDetail(null);
                setHistory(null);
              }}
            >
              {t("Close timeline source")}
            </button>
          </div>
          {history !== null && (
            <section
              aria-label={t("Unified source history")}
              data-detail-target="history"
              className="space-y-2"
            >
              <h4 className="font-medium">{t("Source version history")}</h4>
              <SourceData value={history} />
              <button
                type="button"
                className={button}
                disabled={busy || historyOffset === 0}
                onClick={() => showHistory(Math.max(0, historyOffset - 20))}
              >
                {t("Previous timeline source versions")}
              </button>
              <button
                type="button"
                className={button}
                disabled={busy || historyCount < 20}
                onClick={() => showHistory(historyOffset + 20)}
              >
                {t("Older timeline source versions")}
              </button>
            </section>
          )}
        </article>
      )}
    </section>
  );
}
