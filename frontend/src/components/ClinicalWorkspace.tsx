"use client";

import { useLanguage } from "@/components/LanguageProvider";
import { DeleteRecord } from "./DeleteRecord";

import { type FormEvent, useCallback, useEffect, useId, useMemo, useState } from "react";
import { api, request } from "@/lib/api";
import type { MedicalDocument } from "@/types";
import type {
  ClinicalSource,
  Encounter,
  EncounterInput,
  FollowUp,
  FollowUpInput,
  TaskStatus,
  TimelineEntry,
} from "@/types/clinical";
import { allClinicalResources } from "@/lib/clinical-resources";

const field = "mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm";
const primary =
  "rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50";
const secondary =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50";
const panel = "space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";
const pageSize = 20;
const dateLabel = (date: string) =>
  new Date(`${date}T00:00:00`).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
const timeLabel = (date: string) => new Date(date.endsWith("Z") ? date : `${date}Z`).toLocaleString();
const provenanceLabel = (value: string) =>
  value === "patient_reported"
    ? "Patient-reported"
    : value === "clinician_recorded"
      ? "Clinician-recorded"
      : "Unverified source document";

function Pager({
  offset,
  count,
  onChange,
  busy,
}: {
  offset: number;
  count: number;
  onChange: (offset: number) => void;
  busy: boolean;
}) {
  const { t } = useLanguage();
  if (!offset && count < pageSize) return null;
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <button
        type="button"
        className={secondary}
        disabled={busy || offset === 0}
        onClick={() => onChange(Math.max(0, offset - pageSize))}
      >
        {t("Previous page")}
      </button>
      <span>
        {t("Page")} {offset / pageSize + 1}
      </span>
      <button
        type="button"
        className={secondary}
        disabled={busy || count < pageSize}
        onClick={() => onChange(offset + pageSize)}
      >
        {t("Next page")}
      </button>
    </div>
  );
}

function Sources({
  sources,
  download,
}: {
  sources: ClinicalSource[];
  download: (source: ClinicalSource) => void;
}) {
  const { t } = useLanguage();
  return (
    <div className="space-y-1 text-sm">
      <p className="font-medium">{t("Original sources")}</p>
      {sources.length ? (
        sources.map((source) => (
          <button
            type="button"
            key={source.id}
            className="block max-w-full break-words text-left text-blue-700 underline"
            onClick={() => download(source)}
          >
            {t("Download source:")} {source.title}
          </button>
        ))
      ) : (
        <p className="text-slate-500">
          {t("No source document linked. This is a manually recorded account.")}
        </p>
      )}
    </div>
  );
}

function Attribution({ record }: { record: Encounter | FollowUp }) {
  const { t } = useLanguage();
  return (
    <p className="text-xs text-slate-500">
      {t(provenanceLabel(record.provenance))} {t("by")} {record.recorded_by_name} {t("· Version")}{" "}
      {record.version} · {timeLabel(record.recorded_at)}
    </p>
  );
}

function EncounterEditor({
  initial,
  sources,
  busy,
  onSave,
  onCancel,
  loadMoreSources,
}: {
  initial: Encounter | null;
  sources: ClinicalSource[];
  busy: boolean;
  onSave: (input: EncounterInput) => void;
  onCancel: () => void;
  loadMoreSources: (() => void) | null;
}) {
  const { t } = useLanguage();
  const formId = useId();
  const [title, setTitle] = useState(initial?.title || "");
  const [date, setDate] = useState(initial?.occurred_on || new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState(initial?.notes || "");
  const [selected, setSelected] = useState(initial?.sources.map((source) => source.id) || []);
  const [reason, setReason] = useState("");
  const choices = Array.from(
    new Map([...sources, ...(initial?.sources || [])].map((source) => [source.id, source])).values(),
  );
  function submit(event: FormEvent) {
    event.preventDefault();
    onSave({
      title,
      occurred_on: date,
      notes,
      source_document_ids: selected,
      ...(initial ? { expected_version: initial.version, correction_reason: reason } : {}),
    });
  }
  return (
    <form
      className={panel}
      onSubmit={submit}
      aria-label={initial ? t("Correct consultation") : t("New consultation")}
    >
      <h3 className="font-semibold">{initial ? t("Correct consultation") : t("Add consultation")}</h3>
      <p className="text-sm text-slate-600">
        {t(
          "Record what was reported or documented. Source links support provenance; entries are not independently clinically verified.",
        )}
      </p>
      <fieldset disabled={busy} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            {t("Consultation title")}
            <input
              className={field}
              required
              maxLength={255}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            {t("Consultation date")}
            <input
              className={field}
              required
              type="date"
              max={new Date().toISOString().slice(0, 10)}
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>
        </div>
        <div>
          <label className="block text-sm" htmlFor={`${formId}-notes`}>
            {t("Consultation notes")}
          </label>
          <textarea
            id={`${formId}-notes`}
            className={field}
            rows={5}
            required
            maxLength={20000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
        <fieldset className="space-y-2 rounded-lg border p-3 text-sm">
          <legend className="px-1 font-medium">{t("Link source documents (optional, up to 50)")}</legend>
          {!choices.length && (
            <p className="text-slate-500">{t("Upload an original document to link it here.")}</p>
          )}
          <div className="max-h-48 space-y-2 overflow-y-auto">
            {choices.map((source) => (
              <label key={source.id} className="flex items-start gap-2 break-words">
                <input
                  className="mt-1"
                  type="checkbox"
                  checked={selected.includes(source.id)}
                  disabled={!selected.includes(source.id) && selected.length >= 50}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked ? [...selected, source.id] : selected.filter((id) => id !== source.id),
                    )
                  }
                />
                {source.title}
              </label>
            ))}
          </div>
          {loadMoreSources && (
            <button type="button" className={secondary} onClick={loadMoreSources}>
              {t("Load more source documents")}
            </button>
          )}
        </fieldset>
        {initial && (
          <div>
            <label className="block text-sm">
              {t("Reason for correction")}
              <input
                className={field}
                required
                minLength={5}
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <p className="mt-1 text-xs text-slate-500">
              {t("The original and all earlier corrections remain in history.")}
            </p>
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <button type="submit" className={primary}>
            {busy ? t("Saving…") : initial ? t("Save correction") : t("Save consultation")}
          </button>
          <button type="button" className={secondary} onClick={onCancel}>
            {t("Cancel")}
          </button>
        </div>
      </fieldset>
    </form>
  );
}

function FollowUpEditor({
  initial,
  busy,
  onSave,
  onCancel,
}: {
  initial: FollowUp | null;
  busy: boolean;
  onSave: (input: FollowUpInput) => void;
  onCancel: () => void;
}) {
  const { t } = useLanguage();
  const formId = useId();
  const [title, setTitle] = useState(initial?.title || "");
  const [due, setDue] = useState(initial?.due_on || "");
  const [status, setStatus] = useState<TaskStatus>(initial?.status || "pending");
  const [outcome, setOutcome] = useState(initial?.outcome || "");
  const [reason, setReason] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    onSave({
      title,
      due_on: due,
      status,
      outcome: status === "pending" ? null : outcome,
      ...(initial ? { expected_version: initial.version, correction_reason: reason } : {}),
    });
  }
  return (
    <form
      className={panel}
      onSubmit={submit}
      aria-label={initial ? t("Update follow-up") : t("New follow-up")}
    >
      <h3 className="font-semibold">{initial ? t("Update follow-up") : t("Add follow-up")}</h3>
      <p className="text-sm text-slate-600">
        {t("Track an agreed next step and its reported outcome. No appointment or reminder is sent.")}
      </p>
      <fieldset disabled={busy} className="space-y-4">
        <label className="block text-sm">
          {t("Follow-up title")}
          <input
            className={field}
            required
            maxLength={255}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            {t("Due date")}
            <input
              className={field}
              required
              type="date"
              value={due}
              onChange={(e) => setDue(e.target.value)}
            />
          </label>
          <div>
            <label className="block text-sm" htmlFor={`${formId}-status`}>
              {t("Follow-up status")}
            </label>
            <select
              id={`${formId}-status`}
              className={field}
              value={status}
              onChange={(e) => setStatus(e.target.value as TaskStatus)}
            >
              <option value="pending">{t("Pending")}</option>
              <option value="completed">{t("Completed")}</option>
              <option value="cancelled">{t("Cancelled")}</option>
            </select>
          </div>
        </div>
        {status !== "pending" && (
          <div>
            <label className="block text-sm" htmlFor={`${formId}-outcome`}>
              {status === "completed" ? t("Completion report") : t("Cancellation reason")}
            </label>
            <textarea
              id={`${formId}-outcome`}
              className={field}
              rows={3}
              required
              maxLength={2000}
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
            />
          </div>
        )}
        {initial && (
          <label className="block text-sm">
            {t("Reason for follow-up change")}
            <input
              className={field}
              required
              minLength={5}
              maxLength={500}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
        )}
        <div className="flex flex-wrap gap-2">
          <button type="submit" className={primary}>
            {busy ? t("Saving…") : initial ? t("Save follow-up change") : t("Save follow-up")}
          </button>
          <button type="button" className={secondary} onClick={onCancel}>
            {t("Cancel")}
          </button>
        </div>
      </fieldset>
    </form>
  );
}

export function ClinicalWorkspace({
  patientId,
  canWrite = true,
  canDelete = false,
  documents,
  readResources = allClinicalResources,
  writeResources = allClinicalResources,
}: {
  patientId: string;
  canWrite?: boolean;
  canDelete?: boolean;
  documents: MedicalDocument[];
  readResources?: string[];
  writeResources?: string[];
}) {
  const { t } = useLanguage();
  const readConsultations = readResources.includes("consultations");
  const readFollowUps = readResources.includes("follow_ups");
  const writeConsultations = canWrite && writeResources.includes("consultations");
  const writeFollowUps = canWrite && writeResources.includes("follow_ups");
  const workspaceId = useId();
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [kind, setKind] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [taskOffset, setTaskOffset] = useState(0);
  const [taskFilter, setTaskFilter] = useState("pending");
  const [refresh, setRefresh] = useState(0);
  const [active, setActive] = useState<Encounter | null>(null);
  const [encounterForm, setEncounterForm] = useState<"new" | "edit" | null>(null);
  const [deleteForm, setDeleteForm] = useState(false);
  const [taskForm, setTaskForm] = useState<{ encounterId: string; task: FollowUp | null } | null>(null);
  const [encounterHistory, setEncounterHistory] = useState<Encounter[] | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [taskHistory, setTaskHistory] = useState<{
    task: FollowUp;
    revisions: FollowUp[];
    offset: number;
  } | null>(null);
  const [extraSources, setExtraSources] = useState<MedicalDocument[]>([]);
  const [sourcesDone, setSourcesDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const sources = useMemo(
    () => Array.from(new Map([...documents, ...extraSources].map((doc) => [doc.id, doc])).values()),
    [documents, extraSources],
  );

  const load = useCallback(async () => {
    const timelineQuery = new URLSearchParams({
      patient_id: patientId,
      limit: String(pageSize),
      offset: String(offset),
      search,
    });
    if (kind) timelineQuery.set("kind", kind);
    const taskQuery = new URLSearchParams({
      patient_id: patientId,
      limit: String(pageSize),
      offset: String(taskOffset),
    });
    if (taskFilter) taskQuery.set("status", taskFilter);
    return Promise.all([
      readConsultations
        ? request<TimelineEntry[]>(`/clinical/timeline?${timelineQuery}`)
        : Promise.resolve([] as TimelineEntry[]),
      readFollowUps
        ? request<FollowUp[]>(`/clinical/follow-ups?${taskQuery}`)
        : Promise.resolve([] as FollowUp[]),
    ]);
  }, [patientId, offset, search, kind, taskOffset, taskFilter, readConsultations, readFollowUps]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    load()
      .then(([entries, tasks]) => {
        if (!cancelled) {
          setTimeline(entries);
          setFollowUps(tasks);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message);
          setTimeline([]);
          setFollowUps([]);
          setActive(null);
          setEncounterHistory(null);
          setTaskHistory(null);
          setEncounterForm(null);
          setTaskForm(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [load, refresh]);

  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load or save the record.");
    } finally {
      setBusy(false);
    }
  }
  const download = (source: ClinicalSource) =>
    void act(() => api.documents.download(source.id, source.file_name));
  const openEncounter = (id: string) =>
    void act(async () => {
      setActive(await request<Encounter>(`/clinical/encounters/${id}`));
      setEncounterForm(null);
      setEncounterHistory(null);
      setTaskForm(null);
      setDeleteForm(false);
    });
  const showHistory = (nextOffset: number) =>
    void act(async () => {
      if (!active) return;
      setEncounterHistory(
        await request<Encounter[]>(
          `/clinical/encounters/${active.id}/history?limit=${pageSize}&offset=${nextOffset}`,
        ),
      );
      setHistoryOffset(nextOffset);
    });
  const showTaskHistory = (task: FollowUp, nextOffset = 0) =>
    void act(async () => {
      const revisions = await request<FollowUp[]>(
        `/clinical/follow-ups/${task.id}/history?limit=${pageSize}&offset=${nextOffset}`,
      );
      setTaskHistory({ task, revisions, offset: nextOffset });
    });
  const loadMoreSources = () =>
    void act(async () => {
      const more = await request<MedicalDocument[]>(
        `/documents?patient_id=${patientId}&limit=100&offset=${sources.length}`,
      );
      setExtraSources((previous) => [...previous, ...more]);
      setSourcesDone(more.length < 100);
    });

  return (
    <section className="space-y-5" aria-label={t("Medical timeline and follow-ups")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">{t("Medical timeline & follow-ups")}</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            {t(
              "Consultations stay linked to their original sources. Corrections retain earlier versions and who recorded them.",
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy || loading}
            className={secondary}
            onClick={() => {
              setError("");
              setRefresh((n) => n + 1);
            }}
          >
            {t("Refresh records")}
          </button>
          {writeConsultations && (
            <button
              type="button"
              disabled={busy}
              className={primary}
              onClick={() => {
                setEncounterForm("new");
                setActive(null);
                setEncounterHistory(null);
                setTaskForm(null);
                setDeleteForm(false);
              }}
            >
              {t("Add consultation")}
            </button>
          )}
        </div>
      </div>
      {!canWrite && (
        <p className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
          {t(
            "Patient-approved viewing access. Creating or correcting records requires separate clinical write permission.",
          )}
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {t(error)}
        </p>
      )}
      {message && (
        <p
          role="status"
          className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"
        >
          {t(message)}
        </p>
      )}
      {encounterForm && writeConsultations && (
        <EncounterEditor
          key={encounterForm === "edit" ? `${active?.id}-${active?.version}` : "new"}
          initial={encounterForm === "edit" ? active : null}
          sources={sources}
          busy={busy}
          onCancel={() => setEncounterForm(null)}
          loadMoreSources={sourcesDone || documents.length < 100 ? null : loadMoreSources}
          onSave={(input) =>
            void act(async () => {
              const editing = encounterForm === "edit" && active;
              const record = await request<Encounter>(
                editing ? `/clinical/encounters/${active.id}` : "/clinical/encounters",
                {
                  method: editing ? "PUT" : "POST",
                  body: JSON.stringify(editing ? input : { ...input, patient_id: patientId }),
                },
              );
              setActive(record);
              setEncounterForm(null);
              setEncounterHistory(null);
              setOffset(0);
              setRefresh((n) => n + 1);
              setMessage(
                editing ? "Correction saved. Earlier versions are preserved." : "Consultation recorded.",
              );
            })
          }
        />
      )}
      <div className="grid items-start gap-5 lg:grid-cols-2">
        {readConsultations && (
          <section className={panel} aria-label={t("Chronological timeline")}>
            <h3 className="font-semibold">{t("Chronological record")}</h3>
            <form
              className="flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                setSearch(searchDraft);
                setOffset(0);
              }}
            >
              <label className="min-w-0 flex-1 text-sm">
                {t("Search timeline")}
                <input
                  className={field}
                  value={searchDraft}
                  maxLength={100}
                  onChange={(e) => setSearchDraft(e.target.value)}
                />
              </label>
              <button type="submit" className={secondary} disabled={loading}>
                {t("Search")}
              </button>
              <div className="w-full">
                <label className="text-sm" htmlFor={`${workspaceId}-kind`}>
                  {t("Timeline record type")}
                </label>
                <select
                  id={`${workspaceId}-kind`}
                  className={field}
                  value={kind}
                  onChange={(e) => {
                    setKind(e.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">{t("All records")}</option>
                  <option value="encounter">{t("Consultations")}</option>
                  <option value="document">{t("Documents")}</option>
                </select>
              </div>
            </form>
            {loading ? (
              <p className="text-sm text-slate-500">{t("Loading timeline…")}</p>
            ) : !timeline.length ? (
              <p className="text-sm text-slate-500">{t("No timeline records match this view.")}</p>
            ) : (
              <ol className="divide-y divide-slate-100">
                {timeline.map((entry) => (
                  <li key={`${entry.kind}-${entry.id}`} className="space-y-1 py-4 first:pt-0">
                    <p className="text-xs text-slate-500">
                      {dateLabel(entry.event_date)} ·{" "}
                      {entry.date_basis === "upload_date"
                        ? t("Upload date; clinical date not recorded")
                        : entry.kind === "encounter"
                          ? t("Consultation")
                          : t("Document clinical date")}
                    </p>
                    <button
                      type="button"
                      disabled={busy}
                      className="break-words text-left text-sm font-semibold text-blue-700 hover:underline disabled:opacity-50"
                      onClick={() =>
                        entry.kind === "encounter"
                          ? openEncounter(entry.id)
                          : void act(async () => {
                              const doc = await request<MedicalDocument>(`/documents/${entry.id}`);
                              await api.documents.download(doc.id, doc.file_name);
                            })
                      }
                    >
                      {entry.title}
                    </button>
                    <p className="text-xs text-slate-500">{t(provenanceLabel(entry.provenance))}</p>
                  </li>
                ))}
              </ol>
            )}
            <Pager offset={offset} count={timeline.length} onChange={setOffset} busy={loading || busy} />
          </section>
        )}
        {readFollowUps && (
          <section className={panel} aria-label={t("Follow-up list")}>
            <h3 className="font-semibold">{t("Follow-up tasks")}</h3>
            <div>
              <label className="block text-sm" htmlFor={`${workspaceId}-task-filter`}>
                {t("Show follow-ups")}
              </label>
              <select
                id={`${workspaceId}-task-filter`}
                className={field}
                value={taskFilter}
                onChange={(e) => {
                  setTaskFilter(e.target.value);
                  setTaskOffset(0);
                }}
              >
                <option value="pending">{t("Pending")}</option>
                <option value="completed">{t("Completed")}</option>
                <option value="cancelled">{t("Cancelled")}</option>
                <option value="">{t("All statuses")}</option>
              </select>
            </div>
            <p className="text-xs text-slate-500">
              {t(
                "Due dates use calendar days in UTC. Overdue means a pending task is past its due date; it is not a clinical risk score.",
              )}
            </p>
            {loading ? (
              <p className="text-sm text-slate-500">{t("Loading follow-ups…")}</p>
            ) : !followUps.length ? (
              <p className="text-sm text-slate-500">
                {t("No follow-ups in this view. Open a consultation to add one.")}
              </p>
            ) : (
              <ul className="space-y-3">
                {followUps.map((task) => (
                  <li className="space-y-2 rounded-lg border border-slate-200 p-3" key={task.id}>
                    <p className="break-words font-semibold">{task.title}</p>
                    <p
                      className={`text-sm ${task.overdue ? "font-medium text-amber-800" : "text-slate-600"}`}
                    >
                      {task.overdue
                        ? t("Overdue")
                        : task.status.charAt(0).toUpperCase() + task.status.slice(1)}{" "}
                      {t("· Due")} {dateLabel(task.due_on)}
                    </p>
                    {task.outcome && (
                      <p className="whitespace-pre-wrap break-words text-sm">
                        {t("Reported outcome:")} {task.outcome}
                      </p>
                    )}
                    <Attribution record={task} />
                    {canDelete && (
                      <DeleteRecord
                        key={`${task.id}-${task.version}`}
                        path={`/clinical/follow-ups/${task.id}`}
                        label="Delete follow-up"
                        version={task.version}
                      />
                    )}
                    <div className="flex flex-wrap gap-2">
                      {readConsultations && (
                        <button
                          type="button"
                          disabled={busy}
                          className={secondary}
                          onClick={() => openEncounter(task.encounter_id)}
                        >
                          {t("Open consultation")}
                        </button>
                      )}
                      {writeFollowUps && (
                        <button
                          type="button"
                          disabled={busy}
                          className={secondary}
                          onClick={() =>
                            void act(async () => {
                              const fresh = await request<FollowUp>(`/clinical/follow-ups/${task.id}`);
                              setTaskForm({ encounterId: fresh.encounter_id, task: fresh });
                            })
                          }
                        >
                          {t("Update follow-up")}
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busy}
                        className={secondary}
                        onClick={() => showTaskHistory(task)}
                      >
                        {t("Follow-up history")}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <Pager
              offset={taskOffset}
              count={followUps.length}
              onChange={setTaskOffset}
              busy={loading || busy}
            />
          </section>
        )}
      </div>
      {readConsultations && active && encounterForm !== "edit" && (
        <article className={panel} aria-label={t("Selected consultation")}>
          <div className="flex flex-wrap justify-between gap-2">
            <h3 className="break-words text-lg font-semibold">{active.title}</h3>
            <span className="text-sm text-slate-500">{dateLabel(active.occurred_on)}</span>
          </div>
          <Attribution record={active} />
          <p className="whitespace-pre-wrap break-words text-sm text-slate-700">{active.notes}</p>
          <Sources sources={active.sources} download={download} />
          <div className="flex flex-wrap gap-2">
            {writeConsultations && (
              <button
                type="button"
                className={secondary}
                disabled={busy}
                onClick={() => {
                  setEncounterForm("edit");
                  setEncounterHistory(null);
                  setDeleteForm(false);
                }}
              >
                {t("Correct consultation")}
              </button>
            )}
            {writeFollowUps && (
              <button
                type="button"
                className={primary}
                disabled={busy}
                onClick={() => {
                  setTaskForm({ encounterId: active.id, task: null });
                  setDeleteForm(false);
                }}
              >
                {t("Add follow-up")}
              </button>
            )}
            {canDelete && (
              <button
                type="button"
                className="rounded-lg border border-red-300 px-3 py-2 text-sm font-medium text-red-700 disabled:opacity-50"
                disabled={busy}
                onClick={() => {
                  setDeleteForm(true);
                  setTaskForm(null);
                }}
              >
                {t("Delete consultation")}
              </button>
            )}
            <button type="button" className={secondary} disabled={busy} onClick={() => showHistory(0)}>
              {t("Consultation history")}
            </button>
            <button
              type="button"
              className={secondary}
              disabled={busy}
              onClick={() => openEncounter(active.id)}
            >
              {t("Reload consultation")}
            </button>
            <button
              type="button"
              className={secondary}
              disabled={busy}
              onClick={() => {
                setActive(null);
                setEncounterHistory(null);
                setTaskForm(null);
                setDeleteForm(false);
              }}
            >
              {t("Close consultation")}
            </button>
          </div>
          {deleteForm && canDelete && (
            <form
              aria-label={t("Delete consultation")}
              className="space-y-3 rounded-xl border border-red-200 bg-red-50 p-4"
              onSubmit={(event) => {
                event.preventDefault();
                void act(async () => {
                  await request<void>(
                    `/clinical/encounters/${active.id}?expected_version=${active.version}`,
                    { method: "DELETE" },
                  );
                  setActive(null);
                  setDeleteForm(false);
                  setEncounterForm(null);
                  setEncounterHistory(null);
                  setTaskForm(null);
                  setTaskHistory(null);
                  setOffset(0);
                  setTaskOffset(0);
                  setRefresh((n) => n + 1);
                  setMessage(
                    "Consultation and its history and follow-ups permanently deleted. Original uploaded documents remain in your vault.",
                  );
                });
              }}
            >
              <h4 className="font-semibold text-red-900">{t("Permanently delete this consultation?")}</h4>
              <p className="text-sm text-red-900">
                {t(
                  "All versions of its notes and its follow-ups will be deleted. Original uploaded documents will remain in your vault.",
                )}
              </p>
              <fieldset disabled={busy} className="space-y-3">
                <label className="flex items-start gap-2 text-sm text-red-900">
                  <input type="checkbox" required className="mt-1" />
                  {t("I understand this consultation cannot be restored.")}
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="submit"
                    className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {t("Delete permanently")}
                  </button>
                  <button type="button" className={secondary} onClick={() => setDeleteForm(false)}>
                    {t("Cancel deletion")}
                  </button>
                </div>
              </fieldset>
            </form>
          )}
        </article>
      )}
      {taskForm && writeFollowUps && (
        <FollowUpEditor
          key={taskForm.task ? `${taskForm.task.id}-${taskForm.task.version}` : `new-${taskForm.encounterId}`}
          initial={taskForm.task}
          busy={busy}
          onCancel={() => setTaskForm(null)}
          onSave={(input) =>
            void act(async () => {
              const editing = taskForm.task;
              await request(editing ? `/clinical/follow-ups/${editing.id}` : "/clinical/follow-ups", {
                method: editing ? "PUT" : "POST",
                body: JSON.stringify(editing ? input : { ...input, encounter_id: taskForm.encounterId }),
              });
              setTaskForm(null);
              setTaskHistory(null);
              setTaskOffset(0);
              setRefresh((n) => n + 1);
              setMessage("Follow-up saved with its reporting history.");
            })
          }
        />
      )}
      {encounterHistory && (
        <section className={panel} aria-label={t("Consultation version history")}>
          <div className="flex flex-wrap justify-between gap-2">
            <h3 className="font-semibold">{t("Consultation version history")}</h3>
            <button type="button" className={secondary} onClick={() => setEncounterHistory(null)}>
              {t("Close history")}
            </button>
          </div>
          {encounterHistory.map((record) => (
            <article className="space-y-3 border-t pt-4" key={record.version}>
              <Attribution record={record} />
              <p className="break-words font-medium">
                {record.title} · {dateLabel(record.occurred_on)}
              </p>
              <p className="whitespace-pre-wrap break-words text-sm">{record.notes}</p>
              <p className="break-words text-sm">
                {t("Reason:")} {record.correction_reason}
              </p>
              <Sources sources={record.sources} download={download} />
            </article>
          ))}
          <Pager offset={historyOffset} count={encounterHistory.length} onChange={showHistory} busy={busy} />
        </section>
      )}
      {taskHistory && (
        <section className={panel} aria-label={t("Follow-up version history")}>
          <div className="flex flex-wrap justify-between gap-2">
            <h3 className="font-semibold">{t("Follow-up version history")}</h3>
            <button type="button" className={secondary} onClick={() => setTaskHistory(null)}>
              {t("Close follow-up history")}
            </button>
          </div>
          {taskHistory.revisions.map((record) => (
            <article className="space-y-2 border-t pt-4" key={record.version}>
              <Attribution record={record} />
              <p className="break-words font-medium">
                {record.title} · {record.status} {t("· Due")} {dateLabel(record.due_on)}
              </p>
              {record.outcome && (
                <p className="whitespace-pre-wrap break-words text-sm">
                  {t("Reported outcome:")} {record.outcome}
                </p>
              )}
              <p className="break-words text-sm">
                {t("Reason:")} {record.correction_reason}
              </p>
            </article>
          ))}
          <Pager
            offset={taskHistory.offset}
            count={taskHistory.revisions.length}
            onChange={(next) => showTaskHistory(taskHistory.task, next)}
            busy={busy}
          />
        </section>
      )}
    </section>
  );
}
