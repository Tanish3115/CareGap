"use client";

import { useLanguage } from "@/components/LanguageProvider";
import { DeleteRecord } from "./DeleteRecord";

import { type FormEvent, useEffect, useId, useState } from "react";
import { api, request } from "@/lib/api";

type Source = {
  entry_id: string;
  document_id: string;
  title: string;
  file_name: string;
  prescription_version: number;
  current_source_review_version: number;
  current_prescription_version: number;
  name: string;
  strength: string | null;
  dose: string | null;
  frequency: string | null;
  route: string | null;
  duration: string | null;
  instructions: string | null;
  source_stale: boolean;
  superseded: boolean;
  draft_pending: boolean;
};
type Entry = {
  id: string;
  name: string;
  strength: string | null;
  document_id: string;
  prescription_version: number;
};
type Review = {
  id: string;
  version: number;
  report_version: number;
  assessment: string;
  note: string;
  source_snapshot: Source | null;
  recorded_by_name: string;
  created_at: string;
};
type Report = {
  id: string;
  version: number;
  review_version: number;
  name: string;
  dose: string | null;
  frequency: string | null;
  use_status: string;
  reported_on: string;
  notes: string | null;
  source_entry_id: string | null;
  source: Source | null;
  reason: string;
  recorded_by_name: string;
  latest_review: Review | null;
  review_stale: boolean;
};
type Input = {
  name: string;
  dose: string | null;
  frequency: string | null;
  use_status: string;
  reported_on: string;
  notes: string | null;
  source_entry_id: string | null;
  reason: string;
};
const endpoint = "/clinical/medication-use";
const button =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50";
const field = "mt-1 w-full min-w-0 rounded-lg border border-slate-300 bg-white p-2 text-sm";
const statusLabel = (status: string) =>
  ({
    taking: "Reports taking",
    not_taking: "Reports not taking",
    unknown: "Use uncertain",
    account_reviewed: "Account reviewed",
    discrepancy: "Discrepancy recorded",
    needs_clarification: "Needs clarification",
  })[status] || status;

function Editor({
  initial,
  sources,
  busy,
  loadMore,
  onSave,
  onCancel,
}: {
  initial: Report | null;
  sources: Entry[];
  busy: boolean;
  loadMore: (() => void) | null;
  onSave: (data: Input) => void;
  onCancel: () => void;
}) {
  const { t } = useLanguage();
  const id = useId();
  const [name, setName] = useState(initial?.name || "");
  const [dose, setDose] = useState(initial?.dose || "");
  const [frequency, setFrequency] = useState(initial?.frequency || "");
  const [status, setStatus] = useState(initial?.use_status || "unknown");
  const [date, setDate] = useState(initial?.reported_on || new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState(initial?.notes || "");
  const [source, setSource] = useState(initial?.source_entry_id || "");
  const [reason, setReason] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    onSave({
      name,
      dose: dose.trim() || null,
      frequency: frequency.trim() || null,
      use_status: status,
      reported_on: date,
      notes: notes.trim() || null,
      source_entry_id: source || null,
      reason,
    });
  }
  return (
    <form
      aria-label={t("Medication use report")}
      onSubmit={submit}
      className="space-y-3 rounded-xl border p-4"
    >
      <h3 className="font-semibold">
        {initial ? t("Correct your medication report") : t("Report medication use")}
      </h3>
      <p className="text-sm text-slate-600">
        {t(
          "Describe what you know. Leave unknown details empty. This records your account and does not change a prescription.",
        )}
      </p>
      <fieldset disabled={busy} className="space-y-3">
        <label className="block text-sm" htmlFor={`${id}-name`}>
          {t("Reported medicine name")}
        </label>
        <input
          id={`${id}-name`}
          className={field}
          required
          maxLength={500}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label className="block text-sm" htmlFor={`${id}-status`}>
          {t("Reported use")}
        </label>
        <select
          id={`${id}-status`}
          className={field}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="unknown">{t("Unsure")}</option>
          <option value="taking">{t("Taking")}</option>
          <option value="not_taking">{t("Not taking")}</option>
        </select>
        <label className="block text-sm" htmlFor={`${id}-date`}>
          {t("Report date")}
        </label>
        <input
          id={`${id}-date`}
          className={field}
          type="date"
          required
          max={new Date().toISOString().slice(0, 10)}
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        <label className="block text-sm" htmlFor={`${id}-dose`}>
          {t("Reported dose (optional)")}
        </label>
        <input
          id={`${id}-dose`}
          className={field}
          maxLength={500}
          value={dose}
          onChange={(e) => setDose(e.target.value)}
        />
        <label className="block text-sm" htmlFor={`${id}-frequency`}>
          {t("Reported frequency (optional)")}
        </label>
        <input
          id={`${id}-frequency`}
          className={field}
          maxLength={500}
          value={frequency}
          onChange={(e) => setFrequency(e.target.value)}
        />
        <label className="block text-sm" htmlFor={`${id}-source`}>
          {t("Compare with historical prescription (optional)")}
        </label>
        <select
          id={`${id}-source`}
          className={field}
          value={source}
          onChange={(e) => setSource(e.target.value)}
        >
          <option value="">{t("No prescription linked")}</option>
          {initial?.source && !sources.some((item) => item.id === initial.source_entry_id) && (
            <option value={initial.source_entry_id!}>
              {initial.source.name} {t("· previously linked version")} {initial.source.prescription_version}
            </option>
          )}
          {sources.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} · {item.strength || t("Strength missing")} {t("· prescription version")}{" "}
              {item.prescription_version}
            </option>
          ))}
        </select>
        {loadMore && (
          <button type="button" className={button} onClick={loadMore}>
            {t("Load more prescription entries")}
          </button>
        )}
        <label className="block text-sm" htmlFor={`${id}-notes`}>
          {t("Report notes (optional)")}
        </label>
        <textarea
          id={`${id}-notes`}
          className={field}
          rows={3}
          maxLength={2000}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
        <label className="block text-sm" htmlFor={`${id}-reason`}>
          {t("Reason for medication report")}
        </label>
        <input
          id={`${id}-reason`}
          className={field}
          required
          minLength={5}
          maxLength={500}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <button type="submit" className={button}>
            {t("Save medication report")}
          </button>
          <button type="button" className={button} onClick={onCancel}>
            {t("Cancel medication report")}
          </button>
        </div>
      </fieldset>
    </form>
  );
}

function ReconcileEditor({
  report,
  busy,
  onSave,
  onCancel,
}: {
  report: Report;
  busy: boolean;
  onSave: (data: object) => void;
  onCancel: () => void;
}) {
  const { t } = useLanguage();
  const id = useId();
  const [assessment, setAssessment] = useState("needs_clarification");
  const [note, setNote] = useState("");
  const [checked, setChecked] = useState(false);
  return (
    <form
      aria-label={t("Reconcile medication report")}
      className="space-y-3 rounded border p-3"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({
          expected_report_version: report.version,
          expected_review_version: report.review_version,
          expected_source_review_version: report.source?.current_source_review_version ?? null,
          expected_prescription_version: report.source?.current_prescription_version ?? null,
          assessment,
          note,
          comparison_checked: checked,
        });
      }}
    >
      <fieldset disabled={busy} className="space-y-3">
        <p className="text-sm">
          {t("Review patient report version")} {report.version}{" "}
          {t(
            "and the linked source, if available. Record unresolved differences; this review does not issue an order or verify medication safety.",
          )}
        </p>
        <label className="block text-sm" htmlFor={`${id}-assessment`}>
          {t("Reconciliation assessment")}
        </label>
        <select
          id={`${id}-assessment`}
          className={field}
          value={assessment}
          onChange={(event) => setAssessment(event.target.value)}
        >
          <option value="needs_clarification">{t("Needs clarification")}</option>
          <option value="discrepancy">{t("Discrepancy")}</option>
          <option value="account_reviewed">{t("Account reviewed")}</option>
        </select>
        <label className="block text-sm" htmlFor={`${id}-note`}>
          {t("Reconciliation note")}
        </label>
        <textarea
          id={`${id}-note`}
          required
          minLength={5}
          maxLength={2000}
          rows={4}
          className={field}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            required
            checked={checked}
            onChange={(event) => setChecked(event.target.checked)}
          />
          {t("I compared this patient report with the available source and recorded any unresolved details.")}
        </label>
        <div className="flex flex-wrap gap-2">
          <button type="submit" className={button}>
            {t("Save reconciliation")}
          </button>
          <button type="button" className={button} onClick={onCancel}>
            {t("Cancel reconciliation")}
          </button>
        </div>
      </fieldset>
    </form>
  );
}

export function MedicationUsePanel({
  patientId,
  isPatient = false,
  canReview = false,
}: {
  patientId: string;
  isPatient?: boolean;
  canReview?: boolean;
}) {
  const { t } = useLanguage();
  const [reports, setReports] = useState<Report[]>([]);
  const [active, setActive] = useState<Report | null>(null);
  const [editing, setEditing] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const [sources, setSources] = useState<Entry[]>([]);
  const [sourcesDone, setSourcesDone] = useState(false);
  const [history, setHistory] = useState<Report[] | null>(null);
  const [reviewHistory, setReviewHistory] = useState<Review[] | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setActive(null);
    setHistory(null);
    setReviewHistory(null);
    setEditing(false);
    setReconciling(false);
    request<Report[]>(`${endpoint}?patient_id=${patientId}&limit=20&offset=${offset}`)
      .then((rows) => {
        if (!cancelled) {
          setReports(rows);
          setError("");
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setReports([]);
          setSources([]);
          setError(e.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId, offset, refresh]);
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save medication report");
    } finally {
      setBusy(false);
    }
  }
  async function loadSources(start: number) {
    const rows = await request<Entry[]>(`/medications?patient_id=${patientId}&limit=100&offset=${start}`);
    setSources((previous) => (start ? [...previous, ...rows] : rows));
    setSourcesDone(rows.length < 100);
  }
  function edit(report: Report | null) {
    void act(async () => {
      await loadSources(0);
      setActive(report);
      setEditing(true);
      setReconciling(false);
      setHistory(null);
      setReviewHistory(null);
    });
  }
  function showHistory(reviews: boolean, start = 0) {
    if (!active) return;
    void act(async () => {
      if (reviews) {
        setReviewHistory(
          await request<Review[]>(`${endpoint}/${active.id}/reconciliation/history?limit=20&offset=${start}`),
        );
        setHistory(null);
      } else {
        setHistory(await request<Report[]>(`${endpoint}/${active.id}/history?limit=20&offset=${start}`));
        setReviewHistory(null);
      }
      setHistoryOffset(start);
    });
  }
  return (
    <section
      aria-label={t("Medication use and reconciliation")}
      className="min-w-0 space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-lg font-semibold">{t("Medication use & reconciliation")}</h2>
      <p className="text-sm text-slate-600">
        {t(
          "Patient reports describe use on the report date. Historical prescriptions remain separate. Clinician reviews record comparisons and unresolved details; they do not establish safe doses or issue new prescriptions.",
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
          {t("Refresh medication reports")}
        </button>
        {isPatient && (
          <button type="button" className={button} disabled={busy || loading} onClick={() => edit(null)}>
            {t("Report medication use")}
          </button>
        )}
      </div>
      {loading ? (
        <p>{t("Loading medication reports…")}</p>
      ) : (
        <div className="space-y-2">
          {!reports.length && <p>{t("No medication use reported.")}</p>}
          {reports.map((report) => (
            <button
              type="button"
              key={report.id}
              className="block w-full break-words rounded-lg border p-3 text-left text-sm"
              onClick={() => {
                setActive(report);
                setEditing(false);
                setReconciling(false);
                setHistory(null);
                setReviewHistory(null);
                setMessage("");
              }}
            >
              <span className="font-semibold">{report.name}</span>
              <span className="block">
                {t(statusLabel(report.use_status))} · {report.reported_on} {t("· Version")} {report.version}
              </span>
              <span className="block text-slate-500">
                {report.review_stale
                  ? t("Report or source changed since clinician review")
                  : report.latest_review
                    ? t(statusLabel(report.latest_review.assessment))
                    : t("Awaiting clinician review")}
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
            {t("Previous medication reports")}
          </button>
        )}
        {reports.length === 20 && (
          <button
            type="button"
            className={button}
            disabled={busy || loading}
            onClick={() => setOffset((value) => value + 20)}
          >
            {t("More medication reports")}
          </button>
        )}
      </div>
      {editing && isPatient && (
        <Editor
          key={active ? `${active.id}-${active.version}` : "new"}
          initial={active}
          sources={sources}
          busy={busy}
          loadMore={sourcesDone ? null : () => void act(() => loadSources(sources.length))}
          onCancel={() => setEditing(false)}
          onSave={(data) =>
            void act(async () => {
              await request<Report>(active ? `${endpoint}/${active.id}` : endpoint, {
                method: active ? "PUT" : "POST",
                body: JSON.stringify(
                  active ? { ...data, expected_version: active.version } : { ...data, patient_id: patientId },
                ),
              });
              setOffset(0);
              setRefresh((value) => value + 1);
              setMessage("Patient medication report saved. Historical prescriptions were preserved.");
            })
          }
        />
      )}
      {active && !editing && (
        <article
          aria-label={t("Selected medication report")}
          className="min-w-0 space-y-3 break-words rounded-xl border p-4 text-sm"
        >
          <h3 className="font-semibold">{active.name}</h3>
          {isPatient && (
            <DeleteRecord
              key={`${active.id}-${active.version}-${active.review_version}`}
              path={`/clinical/medication-use/${active.id}`}
              label="Delete medication report"
              version={active.version}
              reviewVersion={active.review_version}
            />
          )}
          <p>
            {t("Patient-reported by")} {active.recorded_by_name} {t("· Version")} {active.version} ·{" "}
            {active.reported_on}
          </p>
          <p>{t(statusLabel(active.use_status))}</p>
          <div className="grid gap-4 md:grid-cols-2">
            <section aria-label={t("Patient medication account")} className="space-y-2 rounded border p-3">
              <h4 className="font-semibold">{t("Patient account")}</h4>
              <p>
                {t("Dose:")} {active.dose || t("Not reported")}
              </p>
              <p>
                {t("Frequency:")} {active.frequency || t("Not reported")}
              </p>
              <p className="whitespace-pre-wrap">{active.notes}</p>
              <p>
                {t("Reason:")} {active.reason}
              </p>
            </section>
            <section
              aria-label={t("Historical prescription comparison")}
              className="space-y-2 rounded border p-3"
            >
              <h4 className="font-semibold">{t("Historical prescription")}</h4>
              {active.source ? (
                <>
                  <p>
                    {active.source.name} · {active.source.strength || t("Strength not documented")}
                  </p>
                  <p>
                    {t("Dose:")} {active.source.dose || t("Not documented")}
                  </p>
                  <p>
                    {t("Frequency:")} {active.source.frequency || t("Not documented")}
                  </p>
                  <p>
                    {t("Route:")} {active.source.route || t("Not documented")} {t("· Duration:")}{" "}
                    {active.source.duration || t("Not documented")}
                  </p>
                  <p>
                    {t("Instructions:")} {active.source.instructions || t("Not documented")}
                  </p>
                  <p>
                    {active.source.title} {t("· Version")} {active.source.prescription_version}
                  </p>
                  {(active.source.source_stale ||
                    active.source.superseded ||
                    active.source.draft_pending) && (
                    <p className="text-amber-800">
                      {t(
                        "Source transcription changed, a newer confirmation exists, or a draft is awaiting review. Compare the original and source history.",
                      )}
                    </p>
                  )}
                  <button
                    type="button"
                    className={button}
                    disabled={busy}
                    onClick={() =>
                      void act(() =>
                        api.documents.download(active.source!.document_id, active.source!.file_name),
                      )
                    }
                  >
                    {t("Download comparison source")}
                  </button>
                </>
              ) : (
                <p>{t("No prescription linked. This is a patient account without a source comparison.")}</p>
              )}
            </section>
          </div>
          {active.latest_review && (
            <div className="space-y-1 rounded border bg-slate-50 p-3">
              <p>
                {t(statusLabel(active.latest_review.assessment))} {t("by")}{" "}
                {active.latest_review.recorded_by_name} {t("· Review")} {active.latest_review.version}{" "}
                {t("of report")} {active.latest_review.report_version}
              </p>
              <p className="whitespace-pre-wrap">{active.latest_review.note}</p>
              {active.review_stale && (
                <p className="text-amber-800">
                  {t("Report or linked source changed since this review. A new clinician review is needed.")}
                </p>
              )}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {isPatient && (
              <button type="button" className={button} disabled={busy} onClick={() => edit(active)}>
                {t("Correct medication report")}
              </button>
            )}
            {canReview && (
              <button type="button" className={button} disabled={busy} onClick={() => setReconciling(true)}>
                {t("Reconcile medication report")}
              </button>
            )}
            <button type="button" className={button} disabled={busy} onClick={() => showHistory(false)}>
              {t("Medication report history")}
            </button>
            <button type="button" className={button} disabled={busy} onClick={() => showHistory(true)}>
              {t("Reconciliation history")}
            </button>
            <button
              type="button"
              className={button}
              onClick={() => {
                setActive(null);
                setHistory(null);
                setReviewHistory(null);
                setReconciling(false);
              }}
            >
              {t("Close medication report")}
            </button>
          </div>
          {reconciling && canReview && (
            <ReconcileEditor
              key={`${active.id}-${active.version}-${active.review_version}`}
              report={active}
              busy={busy}
              onCancel={() => setReconciling(false)}
              onSave={(data) =>
                void act(async () => {
                  await request(`${endpoint}/${active.id}/reconciliation`, {
                    method: "POST",
                    body: JSON.stringify(data),
                  });
                  setRefresh((value) => value + 1);
                  setMessage(
                    "Clinician reconciliation recorded. The patient account and historical prescription were preserved.",
                  );
                })
              }
            />
          )}
        </article>
      )}
      {(history || reviewHistory) && (
        <section aria-label={t("Medication version history")} className="space-y-3 text-sm">
          <h3 className="font-semibold">
            {history ? t("Patient report history") : t("Clinician reconciliation history")}
          </h3>
          {history?.map((row) => (
            <article key={row.version} className="space-y-1 break-words rounded border p-3">
              <p>
                {t("Report")} {row.version} · {row.name} · {row.reported_on} ·{" "}
                {t(statusLabel(row.use_status))}
              </p>
              <p>
                {t("Dose:")} {row.dose || t("Not reported")} {t("· Frequency:")}{" "}
                {row.frequency || t("Not reported")}
              </p>
              <p>{row.notes}</p>
              <p>
                {t("Reason:")} {row.reason}
              </p>
              <p>
                {row.source
                  ? t("Linked source: {value0} · prescription version {value1}", {
                      value0: row.source.name,
                      value1: row.source.prescription_version,
                    })
                  : t("No prescription linked")}
              </p>
            </article>
          ))}
          {reviewHistory?.map((row) => (
            <article key={row.id} className="space-y-1 break-words rounded border p-3">
              <p>
                {t("Review")} {row.version} {t("of report")} {row.report_version} ·{" "}
                {t(statusLabel(row.assessment))} · {row.recorded_by_name}
              </p>
              <p>{row.note}</p>
              <p>
                {row.source_snapshot
                  ? t("Source at review: {value0} · dose {value1} · frequency {value2}", {
                      value0: row.source_snapshot.name,
                      value1: row.source_snapshot.dose || "not documented",
                      value2: row.source_snapshot.frequency || "not documented",
                    })
                  : t("No source linked at review")}
              </p>
            </article>
          ))}
          {!(history?.length || reviewHistory?.length) && <p>{t("No versions recorded.")}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={button}
              disabled={busy || historyOffset === 0}
              onClick={() => showHistory(!!reviewHistory, Math.max(0, historyOffset - 20))}
            >
              {t("Previous medication versions")}
            </button>
            <button
              type="button"
              className={button}
              disabled={busy || (history || reviewHistory || []).length < 20}
              onClick={() => showHistory(!!reviewHistory, historyOffset + 20)}
            >
              {t("Older medication versions")}
            </button>
            <button
              type="button"
              className={button}
              onClick={() => {
                setHistory(null);
                setReviewHistory(null);
              }}
            >
              {t("Close medication history")}
            </button>
          </div>
        </section>
      )}
    </section>
  );
}
