"use client";

import { useLanguage } from "@/components/LanguageProvider";

import { useCallback, useEffect, useId, useState } from "react";
import { request } from "@/lib/api";
import { MedicationCodingEditor, type MedicationCoding } from "./MedicationCodingEditor";

const fields = ["name", "strength", "dose", "route", "frequency", "duration", "instructions"] as const;
type Field = (typeof fields)[number];
const contextFields = ["doctor_name", "consultation_date", "clinic"] as const;
type ContextKey = (typeof contextFields)[number];
type EvidenceField = Field | ContextKey | "follow_up_instructions" | "test_recommendations";
type Context = Record<ContextKey, Evidence | null> & {
  follow_up_instructions: Evidence[];
  test_recommendations: Evidence[];
};
const emptyContext = (): Context => ({
  doctor_name: null,
  consultation_date: null,
  clinic: null,
  follow_up_instructions: [],
  test_recommendations: [],
});
type Evidence = { value: string; start: number; end: number; checked: boolean; uncertain: boolean };
type Item = { source_start: number; source_end: number; coding: MedicationCoding | null } & Record<
  Field,
  Evidence | null
>;
type Draft = {
  id: string;
  document_id: string;
  patient_id: string;
  version: number;
  source_review_version: number;
  source_text: string;
  source_stale: boolean;
  state: "draft" | "clinician_confirmed";
  items: Item[];
  context: Context;
  missing_fields: string[][];
  author_name: string;
  author_role: string;
  reason: string;
  extractor_version: string;
  can_edit: boolean;
  can_confirm: boolean;
};
type Entry = {
  id: string;
  name: string;
  strength: string | null;
  dose: string | null;
  frequency: string | null;
  route: string | null;
  duration: string | null;
  instructions: string | null;
  needs_clarification: boolean;
  missing_fields: string[];
  source_stale: boolean;
  draft_pending: boolean;
  confirmed_by_name: string;
  coding: MedicationCoding | null;
};
const button =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold disabled:opacity-50";
const input = "mt-1 w-full min-w-0 rounded border border-slate-300 bg-white p-2 text-xs";
const label = (field: EvidenceField) =>
  (
    ({
      name: "Medication name",
      doctor_name: "Recorded doctor name",
      consultation_date: "Source consultation date",
      clinic: "Source clinic or hospital",
      follow_up_instructions: "Source follow-up instruction",
      test_recommendations: "Source test recommendation",
    }) as Partial<Record<EvidenceField, string>>
  )[field] || field.charAt(0).toUpperCase() + field.slice(1);
const slice = (text: string, start: number, end: number) => Array.from(text).slice(start, end).join("");

function sourceLines(text: string) {
  let offset = 0;
  return (text.match(/[^\n]*\n|[^\n]+$/g) || [])
    .map((raw) => {
      const value = raw.replace(/\r?\n$/, "");
      const line = { value, start: offset, end: offset + Array.from(value).length };
      offset += Array.from(raw).length;
      return line;
    })
    .filter((line) => line.value.trim() && line.end - line.start <= 2000);
}

function matches(quote: string, value: string, offset: number) {
  const result: number[] = [];
  if (!value.trim()) return result;
  let from = 0;
  while (from <= quote.length) {
    const index = quote.indexOf(value, from);
    if (index < 0) break;
    result.push(offset + Array.from(quote.slice(0, index)).length);
    from = index + Math.max(1, value.length);
  }
  return result;
}

function FieldEditor({
  field,
  value,
  quote,
  offset,
  rowNumber,
  onChange,
  contextField = false,
}: {
  field: EvidenceField;
  value: Evidence | null;
  quote: string;
  offset: number;
  rowNumber: number;
  onChange: (value: Evidence | null) => void;
  contextField?: boolean;
}) {
  const { t } = useLanguage();
  const id = useId();
  const suffix = contextField ? "" : ` \u00b7 row ${rowNumber}`;
  const occurrences = matches(quote, value?.value || "", offset);
  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium" htmlFor={id}>
        {t(label(field))}
        {suffix}
      </label>
      <input
        id={id}
        maxLength={500}
        value={value?.value || ""}
        placeholder={t("Not documented")}
        className={input}
        onChange={(event) => {
          const text = event.target.value;
          if (!text) {
            onChange(null);
            return;
          }
          const found = matches(quote, text, offset);
          const start = found.length === 1 ? found[0] : -1;
          onChange({
            value: text,
            start,
            end: start < 0 ? -1 : start + Array.from(text).length,
            checked: false,
            uncertain: true,
          });
        }}
      />
      {value && occurrences.length > 1 && (
        <label className="block text-xs text-slate-600">
          {t("Source occurrence for")} {t(label(field))}
          {suffix}
          <select
            className={input}
            value={value.start >= 0 ? value.start : ""}
            onChange={(event) => {
              const start = Number(event.target.value);
              onChange({
                ...value,
                start,
                end: start + Array.from(value.value).length,
                checked: false,
                uncertain: true,
              });
            }}
          >
            <option value="" disabled>
              {t("Choose the matching occurrence")}
            </option>
            {occurrences.map((start, index) => (
              <option key={start} value={start}>
                {t("Match")} {index + 1}:{" "}
                {slice(
                  quote,
                  Math.max(0, start - offset - 15),
                  start - offset + Array.from(value.value).length + 15,
                )}
              </option>
            ))}
          </select>
        </label>
      )}
      {value && value.start < 0 && (
        <p className="text-xs text-red-700">
          {t("Choose exact text from the source passage before saving.")}
        </p>
      )}
      {value && (
        <label className="flex items-start gap-2 text-xs">
          <input
            type="checkbox"
            disabled={value.start < 0}
            checked={value.checked && !value.uncertain}
            onChange={(event) =>
              onChange({ ...value, checked: event.target.checked, uncertain: !event.target.checked })
            }
          />
          {t("Checked")} {t(label(field).toLowerCase())} {t("against original")}
          {suffix}
        </label>
      )}
    </div>
  );
}

export function PrescriptionPanel({
  documentId,
  sourceReviewVersion,
  sourceText,
  canEdit,
}: {
  documentId: string;
  sourceReviewVersion: number;
  sourceText: string;
  canEdit: boolean;
}) {
  const { t } = useLanguage();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [context, setContext] = useState<Context>(emptyContext);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [reason, setReason] = useState("");
  const [sourceChecked, setSourceChecked] = useState(false);
  const [limitsChecked, setLimitsChecked] = useState(false);
  const [lineIndex, setLineIndex] = useState(0);
  const [history, setHistory] = useState<Draft[] | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [refresh, setRefresh] = useState(0);
  const lines = sourceLines(draft?.source_text || sourceText);
  const invalid =
    items.some((item) => fields.some((field) => item[field] && item[field]!.start < 0)) ||
    Object.values(context)
      .flat()
      .some((value) => value && value.start < 0);
  const adopt = useCallback((next: Draft | null) => {
    setDraft(next);
    // Each reviewer must check the source themselves; earlier actors' checks are not preselected.
    setItems(
      (next?.items || []).map((item) => {
        const copy = { ...item };
        copy.coding = item.coding ? { ...item.coding, checked: false, uncertain: true } : null;
        for (const field of fields) {
          const value = item[field];
          copy[field] = value ? { ...value, checked: false, uncertain: true } : null;
        }
        return copy;
      }),
    );
    const nextContext = next?.context || emptyContext();
    const uncheck = (value: Evidence) => ({ ...value, checked: false, uncertain: true });
    setContext({
      ...Object.fromEntries(
        contextFields.map((key) => [key, nextContext[key] ? uncheck(nextContext[key]!) : null]),
      ),
      follow_up_instructions: nextContext.follow_up_instructions.map(uncheck),
      test_recommendations: nextContext.test_recommendations.map(uncheck),
    } as Context);
    setReason("");
    setSourceChecked(false);
    setLimitsChecked(false);
  }, []);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setEntries(null);
    setHistory(null);
    request<Draft | null>(`/documents/${documentId}/prescription`)
      .then((next) => {
        if (!cancelled) {
          adopt(next);
          setError("");
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message);
          adopt(null);
          setEntries(null);
          setHistory(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, sourceReviewVersion, refresh, adopt]);

  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load or save prescription draft");
    } finally {
      setBusy(false);
    }
  }
  function generate() {
    void act(async () => {
      adopt(
        await request<Draft>(`/documents/${documentId}/prescription/generate`, {
          method: "POST",
          body: JSON.stringify({
            expected_version: draft?.version || 0,
            source_review_version: sourceReviewVersion,
          }),
        }),
      );
      setHistory(null);
      setEntries(null);
      setMessage("Draft generated from explicit labels. Review every field; missing values remain empty.");
    });
  }
  function save(confirm: boolean) {
    void act(async () => {
      const next = await request<Draft>(`/documents/${documentId}/prescription`, {
        method: "POST",
        body: JSON.stringify({
          expected_version: draft?.version || 0,
          source_review_version: sourceReviewVersion,
          items,
          context,
          reason,
          source_checked: sourceChecked,
          confirm,
          missing_fields_acknowledged: limitsChecked,
        }),
      });
      adopt(next);
      setHistory(null);
      setEntries(null);
      setMessage(
        confirm
          ? "Clinician-reviewed historical entries recorded. This does not issue a prescription or establish current use."
          : "Prescription draft saved. No medication entries were created.",
      );
    });
  }
  function showEntries() {
    if (!draft) return;
    void act(async () =>
      setEntries(
        await request<Entry[]>(`/medications?patient_id=${draft.patient_id}&document_id=${documentId}`),
      ),
    );
  }
  function showHistory(offset: number) {
    void act(async () => {
      setHistory(
        await request<Draft[]>(`/documents/${documentId}/prescription/history?limit=10&offset=${offset}`),
      );
      setHistoryOffset(offset);
    });
  }

  return (
    <section
      aria-label={t("Structured prescription draft")}
      className="space-y-3 border-t border-slate-200 pt-3 text-xs"
    >
      <h5 className="text-sm font-semibold">{t("Structured prescription draft")}</h5>
      <p className="text-slate-600">
        {t(
          "Generate a draft from clearly labelled entries, or add a source passage manually. Check each value against the original; missing details stay empty. Drafts do not establish current medication use or dose safety.",
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
      {loading ? (
        <p>{t("Loading prescription draft…")}</p>
      ) : (
        <>
          {draft && (
            <p className="font-medium">
              {t("Version")} {draft.version} ·{" "}
              {draft.state === "draft"
                ? t("Unconfirmed draft")
                : t("Clinician-reviewed prescription transcription")}{" "}
              · {draft.author_name}
            </p>
          )}
          {draft?.source_stale && (
            <p className="rounded border border-amber-300 bg-amber-50 p-2 text-amber-900">
              {t(
                "The source transcription changed. Rebuild from the current transcription before saving or confirming. Earlier versions remain in history.",
              )}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {canEdit && (
              <button type="button" className={button} disabled={busy} onClick={generate}>
                {draft ? t("Rebuild from current transcription") : t("Generate prescription draft")}
              </button>
            )}
            <button
              type="button"
              className={button}
              disabled={busy}
              onClick={() => setRefresh((value) => value + 1)}
            >
              {t("Reload prescription draft")}
            </button>
            {draft && (
              <>
                <button type="button" className={button} disabled={busy} onClick={() => showHistory(0)}>
                  {t("Prescription draft history")}
                </button>
                <button type="button" className={button} disabled={busy} onClick={showEntries}>
                  {t("View documented entries")}
                </button>
              </>
            )}
          </div>
          {draft && (
            <>
              {!items.length && (
                <p>
                  {t(
                    "No supported medication lines found. Add a source passage manually; nothing was inferred.",
                  )}
                </p>
              )}
              <fieldset disabled={busy || !canEdit || draft.source_stale} className="space-y-4">
                <details className="space-y-3 rounded-lg border p-3">
                  <summary className="cursor-pointer font-semibold">
                    {t("Prescription context and recommendations")}
                  </summary>
                  <p>
                    {t(
                      "Copy only exact source text. A date is preserved as written; it does not replace the document date or book care. Every supplied value needs its own review before confirmation.",
                    )}
                  </p>
                  {contextFields.map((field) => (
                    <FieldEditor
                      key={field}
                      contextField
                      field={field}
                      value={context[field]}
                      quote={draft.source_text}
                      offset={0}
                      rowNumber={0}
                      onChange={(value) => setContext((previous) => ({ ...previous, [field]: value }))}
                    />
                  ))}
                  {(["follow_up_instructions", "test_recommendations"] as const).map((field) => (
                    <div className="space-y-2" key={field}>
                      <h6 className="font-semibold">{t(label(field))}</h6>
                      {context[field].map((value, index) => (
                        <div className="space-y-2 rounded border p-2" key={index}>
                          <FieldEditor
                            contextField
                            field={field}
                            value={value}
                            quote={draft.source_text}
                            offset={0}
                            rowNumber={index + 1}
                            onChange={(next) =>
                              setContext((previous) => ({
                                ...previous,
                                [field]: next
                                  ? previous[field].map((entry, i) => (i === index ? next : entry))
                                  : previous[field].filter((_, i) => i !== index),
                              }))
                            }
                          />
                          <button
                            type="button"
                            className={button}
                            onClick={() =>
                              setContext((previous) => ({
                                ...previous,
                                [field]: previous[field].filter((_, i) => i !== index),
                              }))
                            }
                          >
                            {t("Remove source recommendation")}
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        className={button}
                        disabled={context[field].length >= 20}
                        onClick={() =>
                          setContext((previous) => ({
                            ...previous,
                            [field]: [
                              ...previous[field],
                              { value: "", start: -1, end: -1, checked: false, uncertain: true },
                            ],
                          }))
                        }
                      >
                        {t("Add")} {t(label(field).toLowerCase())}
                      </button>
                    </div>
                  ))}
                </details>
                {items.map((item, index) => (
                  <article
                    key={index}
                    className="space-y-3 rounded-lg border border-slate-300 bg-white p-3"
                    aria-label={t("Prescription row {value0}", { value0: index + 1 })}
                  >
                    <p className="font-semibold">
                      {t("Source row")} {index + 1}
                    </p>
                    <blockquote className="max-h-36 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-100 p-2">
                      {slice(draft.source_text, item.source_start, item.source_end)}
                    </blockquote>
                    {fields.map((field) => (
                      <FieldEditor
                        key={field}
                        field={field}
                        value={item[field]}
                        quote={slice(draft.source_text, item.source_start, item.source_end)}
                        offset={item.source_start}
                        rowNumber={index + 1}
                        onChange={(value) =>
                          setItems((previous) =>
                            previous.map((row, rowIndex) =>
                              rowIndex === index
                                ? { ...row, [field]: value, coding: field === "name" ? null : row.coding }
                                : row,
                            ),
                          )
                        }
                      />
                    ))}
                    <MedicationCodingEditor
                      key={item.name?.value || "missing"}
                      documentId={documentId}
                      sourceReviewVersion={draft.source_review_version}
                      item={item}
                      coding={item.coding || null}
                      onChange={(coding) =>
                        setItems((previous) =>
                          previous.map((row, rowIndex) => (rowIndex === index ? { ...row, coding } : row)),
                        )
                      }
                    />
                    <p className="text-amber-800">
                      {t("Missing:")} {fields.filter((field) => !item[field]).join(", ") || t("None")}
                    </p>
                    <button
                      type="button"
                      className={button}
                      onClick={() =>
                        setItems((previous) => previous.filter((_, rowIndex) => rowIndex !== index))
                      }
                    >
                      {t("Remove source row")} {index + 1}
                    </button>
                  </article>
                ))}
                {items.length < 50 && lines.length > 0 && (
                  <div className="space-y-2">
                    <label className="block">
                      {t("Source passage for a manual row")}
                      <select
                        className={input}
                        value={lineIndex}
                        onChange={(event) => setLineIndex(Number(event.target.value))}
                      >
                        {lines.map((line, index) => (
                          <option key={index} value={index}>
                            {line.value.slice(0, 140)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      className={button}
                      onClick={() => {
                        const line = lines[Math.min(lineIndex, lines.length - 1)];
                        setItems((previous) => [
                          ...previous,
                          {
                            source_start: line.start,
                            source_end: line.end,
                            ...Object.fromEntries(fields.map((field) => [field, null])),
                          } as Item,
                        ]);
                      }}
                    >
                      {t("Add source-bound row")}
                    </button>
                  </div>
                )}
                <label className="block">
                  {t("Reason for prescription review")}
                  <input
                    className={input}
                    required
                    minLength={5}
                    maxLength={500}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                  />
                </label>
                <label className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    checked={sourceChecked}
                    onChange={(event) => setSourceChecked(event.target.checked)}
                  />
                  {t("I checked the original prescription and its patient/date association.")}
                </label>
                <label className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    checked={limitsChecked}
                    onChange={(event) => setLimitsChecked(event.target.checked)}
                  />
                  {t("I acknowledge missing or repeated source fields that need clarification.")}
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={button}
                    disabled={invalid || !sourceChecked || reason.trim().length < 5}
                    onClick={() => save(false)}
                  >
                    {t("Save prescription draft")}
                  </button>
                  {draft.can_confirm && (
                    <button
                      type="button"
                      className="rounded-lg bg-blue-600 px-3 py-2 font-semibold text-white disabled:opacity-50"
                      disabled={invalid || !sourceChecked || reason.trim().length < 5}
                      onClick={() => save(true)}
                    >
                      {t("Confirm prescription transcription")}
                    </button>
                  )}
                </div>
              </fieldset>
              {!draft.can_confirm && (
                <p className="text-slate-500">
                  {t(
                    "Only an authorized verified clinician can record clinician-reviewed historical entries. Drafts do not establish current medication use.",
                  )}
                </p>
              )}
            </>
          )}
        </>
      )}
      {entries && (
        <section aria-label={t("Documented prescription entries")} className="space-y-2">
          <h6 className="font-semibold">{t("Documented prescription entries")}</h6>
          <p>
            {t(
              "These describe the source prescription. Current use, dispensing and medication safety are not established.",
            )}
          </p>
          {!entries.length && <p>{t("No clinician-confirmed entries.")}</p>}
          {entries.map((entry) => (
            <article key={entry.id} className="space-y-1 rounded border bg-white p-2">
              <p className="font-medium">
                {entry.name} · {entry.strength || t("Strength not documented")}
              </p>
              <p>
                {t("Dose:")} {entry.dose || t("Not documented")} {t("· Frequency:")}{" "}
                {entry.frequency || t("Not documented")}
              </p>
              <p>
                {t("Route:")} {entry.route || t("Not documented")} {t("· Duration:")}{" "}
                {entry.duration || t("Not documented")}
              </p>
              <p className="whitespace-pre-wrap break-words">
                {t("Instructions:")} {entry.instructions || t("Not documented")}
              </p>
              <p>
                {t("Reviewed by")} {entry.confirmed_by_name}
              </p>
              {entry.coding && (
                <div className="break-words">
                  <p>
                    {t("Medication terminology")}: {entry.coding.display} · {entry.coding.system} ·{" "}
                    {entry.coding.code} · {entry.coding.release}
                  </p>
                  <p>{entry.coding.evidence_reference}</p>
                  {entry.coding.mode === "synthetic" && (
                    <p className="text-amber-900">
                      {t("Synthetic terminology fixture; not a real medication mapping.")}
                    </p>
                  )}
                </div>
              )}
              {entry.needs_clarification && (
                <p className="text-amber-800">
                  {t("Needs clarification. Missing fields:")}{" "}
                  {entry.missing_fields.join(", ") || t("Repeated source name")}
                </p>
              )}
              {entry.source_stale && (
                <p className="text-amber-800">
                  {t("Source transcription has changed since this confirmation.")}
                </p>
              )}
              {entry.draft_pending && (
                <p className="text-amber-800">{t("A newer draft is awaiting clinician review.")}</p>
              )}
            </article>
          ))}
        </section>
      )}
      {history && (
        <section aria-label={t("Prescription version history")} className="space-y-2">
          <h6 className="font-semibold">{t("Prescription version history")}</h6>
          {history.map((row) => (
            <article key={row.version} className="rounded border bg-white p-2">
              <p>
                {t("Version")} {row.version} ·{" "}
                {row.state === "draft" ? t("Draft") : t("Clinician-reviewed transcription")} ·{" "}
                {row.author_name}
              </p>
              <p>
                {t("Source review")} {row.source_review_version} · {row.items.length} {t("row(s)")}
              </p>
              <p>
                {t("Reason:")} {row.reason}
              </p>
              {contextFields.map(
                (field) =>
                  row.context?.[field] && (
                    <p key={field}>
                      {t(label(field))}: {row.context[field]!.value}
                    </p>
                  ),
              )}
              {[
                ...(row.context?.follow_up_instructions || []),
                ...(row.context?.test_recommendations || []),
              ].map((value, index) => (
                <p key={index}>{value.value}</p>
              ))}
              {row.items.map((item, index) => (
                <p className="break-words" key={index}>
                  {item.name?.value || t("Name unresolved")} · {item.strength?.value || t("Strength missing")}
                </p>
              ))}
            </article>
          ))}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={button}
              disabled={busy || historyOffset === 0}
              onClick={() => showHistory(Math.max(0, historyOffset - 10))}
            >
              {t("Previous draft versions")}
            </button>
            <button
              type="button"
              className={button}
              disabled={busy || history.length < 10}
              onClick={() => showHistory(historyOffset + 10)}
            >
              {t("Older draft versions")}
            </button>
            <button type="button" className={button} onClick={() => setHistory(null)}>
              {t("Close draft history")}
            </button>
          </div>
        </section>
      )}
    </section>
  );
}
