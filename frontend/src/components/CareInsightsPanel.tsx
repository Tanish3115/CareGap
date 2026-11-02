"use client";

import { languages } from "@/lib/i18n";
import { useLanguage } from "@/components/LanguageProvider";
import { ResearchStudyPanel } from "./ResearchStudyPanel";

import { useId, useState } from "react";
import { api, request } from "@/lib/api";
import type { HealthRecord } from "./StructuredCarePanel";
import { allClinicalResources, resourceForKind } from "@/lib/clinical-resources";

type Work = {
  record: HealthRecord;
  overdue: boolean;
  rule_suggestions: { action: string; reason: string }[];
  basis: string;
};
type Pref = { version: number; enabled: boolean; channels: string[]; language: string; mode: string };
type Delivery = {
  id: string;
  channel: string;
  mode: string;
  status: string;
  body: string;
  created_at: string;
  stale: boolean;
};
type Fact = {
  category: string;
  provenance: string;
  source_id: string;
  source_version: number;
  source_path: string;
  title: string;
  date: string;
  details: Record<string, unknown>;
  documents: { id: string; title: string; file_name: string }[];
};
type Overview = { mode: string; facts: Fact[]; has_more: boolean; missing_information: string };
type Indicator = { type: string; evidence_ids: string[]; message: string; evidence?: string };
type Review = {
  approved_knowledge?: {
    status: string;
    reference: string | null;
    release: string | null;
    eligible_sources: number;
    excluded_sources: number;
    assessed_pairs: number;
    unassessed_pairs: number;
    findings: { finding: string; message: string; evidence_reference: string }[];
  };
  evidence: { id: string; name: string; kind: string; source_path: string; source_version: number }[];
  indicators: Indicator[];
  synthetic_demonstrations: Indicator[];
  clinical_knowledge_provider: string;
  clinical_safety_checked: boolean;
  allergy_records_included: boolean;
  truncated: boolean;
  limitations: string;
};
type Metric = {
  count: number;
  precision: number;
  recall: number;
  average_precision: number;
  false_positive_rate: number;
  brier: number;
  calibration: {
    lower: number;
    upper: number;
    count: number;
    predicted: number | null;
    observed: number | null;
  }[];
};
type Evaluation = {
  mode: string;
  model: string;
  version: string;
  seed: number;
  test: Metric;
  constant_baseline: Metric;
  subgroups: Record<string, Metric>;
  cohorts: Record<string, { count: number; first: string; last: string }>;
  limitations: string[];
};
type Bundle = { entry: { resource: { resourceType: string } }[]; link?: { url: string }[] };
const button =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50";
const field = "mt-1 w-full min-w-0 rounded-lg border border-slate-300 bg-white p-2 text-sm";
const panel = "min-w-0 space-y-3 rounded-xl border p-4";
const human = (text: string) => text.replaceAll("_", " ");
function saveJson(value: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function CareInsightsPanel({
  patientId,
  isPatient = false,
  canWrite = false,
  readResources = allClinicalResources,
  writeResources = allClinicalResources,
}: {
  patientId: string;
  isPatient?: boolean;
  canWrite?: boolean;
  readResources?: string[];
  writeResources?: string[];
}) {
  const { t, locale } = useLanguage();
  const careRead = readResources.includes("care_plans");
  const careWrite = canWrite && writeResources.includes("care_plans");
  const fhirRead = Object.values(resourceForKind).some((group) => readResources.includes(group));
  const fhirWrite =
    canWrite && ["diagnoses", "allergies", "labs"].some((group) => writeResources.includes(group));
  const formId = useId();
  const [work, setWork] = useState<Work[] | null>(null);
  const [workOffset, setWorkOffset] = useState(0);
  const [pref, setPref] = useState<Pref | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[] | null>(null);
  const [deliveryOffset, setDeliveryOffset] = useState(0);
  const [checked, setChecked] = useState<string[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [overviewOffset, setOverviewOffset] = useState(0);
  const [review, setReview] = useState<Review | null>(null);
  const [source, setSource] = useState<unknown>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [caseValues, setCaseValues] = useState({
    prior_missed: 2,
    prior_incomplete_referrals: 1,
    days_since_visit: 30,
    lead_days: 7,
    barrier_count: 1,
  });
  const [interventions, setInterventions] = useState<{
    events: unknown[];
    group_counts: unknown;
    has_more: boolean;
    limitations: string;
  } | null>(null);
  const [interventionOffset, setInterventionOffset] = useState(0);
  const [caseResult, setCaseResult] = useState<{
    synthetic_probability: number;
    signed_log_odds_contributions: Record<string, number>;
  } | null>(null);
  const [fhir, setFhir] = useState<Bundle | null>(null);
  const [fhirOffset, setFhirOffset] = useState(0);
  const [rawBundle, setRawBundle] = useState("");
  const [reason, setReason] = useState("");
  const [sourceChecked, setSourceChecked] = useState(false);
  const [preview, setPreview] = useState<{ records: unknown[]; warning: string } | null>(null);
  const [previewBody, setPreviewBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState<string | { key: string; count: number }>("");
  const language = locale;
  const hi = language === "hi";
  function clearClinical() {
    setWork(null);
    setDeliveries(null);
    setOverview(null);
    setReview(null);
    setSource(null);
    setFhir(null);
    setPreview(null);
    setPreviewBody("");
    setInterventions(null);
  }
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      clearClinical();
      setError(e instanceof Error ? e.message : "Unable to load care information");
    } finally {
      setBusy(false);
    }
  }
  function loadWork(offset = 0) {
    void act(async () => {
      setWork(
        await request<Work[]>(`/clinical/care-worklist?patient_id=${patientId}&limit=20&offset=${offset}`),
      );
      setChecked([]);
      setWorkOffset(offset);
    });
  }
  function loadHistory(offset = 0) {
    void act(async () => {
      setDeliveries(
        await request<Delivery[]>(`/notifications/history?patient_id=${patientId}&limit=20&offset=${offset}`),
      );
      setDeliveryOffset(offset);
    });
  }
  function loadOverview(offset = 0) {
    void act(async () => {
      setOverview(
        await request<Overview>(`/clinical/overview?patient_id=${patientId}&limit=20&offset=${offset}`),
      );
      setOverviewOffset(offset);
    });
  }
  function exportPage(offset = 0) {
    void act(async () => {
      const result = await request<Bundle>(
        `/clinical/fhir/export?patient_id=${patientId}&limit=50&offset=${offset}`,
      );
      setFhir(result);
      setFhirOffset(offset);
      saveJson(result, `caregap-r4-${offset}.json`);
    });
  }
  function loadInterventions(offset = 0) {
    void act(async () => {
      setInterventions(
        await request(`/clinical/intervention-outcomes?patient_id=${patientId}&limit=50&offset=${offset}`),
      );
      setInterventionOffset(offset);
    });
  }
  return (
    <section
      aria-label={t("Care coordination and source overview")}
      className="min-w-0 space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">
          {hi ? "देखभाल समन्वय और स्रोत समीक्षा" : t("Care coordination & source overview")}
        </h2>
      </div>
      <p className="text-sm text-slate-600">
        {hi
          ? "यह सूची दर्ज तिथियों और स्थिति पर आधारित है। अनुस्मारक केवल स्थानीय परीक्षण हैं; कोई वास्तविक संदेश नहीं भेजा जाता। रिकॉर्ड का मूल पाठ अनुवादित नहीं है।"
          : t(
              "This worklist uses recorded dates and outcomes. Local mock reminders send no real messages. Source extracts, literal medication comparisons and synthetic research results are shown separately.",
            )}
      </p>
      {error && (
        <p role="alert" className="break-words text-red-700">
          {t(error)}
        </p>
      )}
      {message && (
        <p role="status" className="break-words text-emerald-800">
          {typeof message === "string" ? t(message) : t(message.key, { value0: message.count })}
        </p>
      )}
      {careRead && (
        <section aria-label={t("Care gap worklist")} className={panel}>
          <h3 className="font-semibold">{hi ? "अपूर्ण देखभाल कार्य" : t("Care worklist")}</h3>
          <button type="button" className={button} disabled={busy} onClick={() => loadWork()}>
            {hi ? "देखभाल सूची ताज़ा करें" : t("Refresh care worklist")}
          </button>
          {work && (
            <>
              {!work.length && (
                <p>
                  {t(
                    "No unresolved structured care events due within seven days. Consultation-linked follow-ups remain in their own list.",
                  )}
                </p>
              )}
              {work.map((item) => (
                <article key={item.record.id} className="space-y-2 break-words rounded border p-3 text-sm">
                  <h4 className="font-semibold">{item.record.title}</h4>
                  <p>
                    {t(human(item.record.kind))} {t("· due")} {String(item.record.data.due_on)} ·{" "}
                    {t(human(String(item.record.data.status)))} ·{" "}
                    {item.overdue ? t("Overdue") : t("Review care status")}
                  </p>
                  <p>
                    {item.record.provenance === "patient_reported"
                      ? t("Patient-reported")
                      : t("Clinician-recorded")}{" "}
                    {t("· Version")} {item.record.version}
                  </p>
                  {item.rule_suggestions.map((rule) => (
                    <p key={rule.action}>
                      {t("Staff review:")} {t(human(rule.action))} — {rule.reason}
                    </p>
                  ))}
                  <p className="text-xs text-slate-500">
                    {item.basis} {t("Record interventions and outcomes in Clinical records & care events.")}
                  </p>
                  {careWrite && (
                    <>
                      <label className="flex items-start gap-2">
                        <input
                          type="checkbox"
                          checked={checked.includes(item.record.id)}
                          onChange={(event) =>
                            setChecked((previous) =>
                              event.target.checked
                                ? [...previous, item.record.id]
                                : previous.filter((id) => id !== item.record.id),
                            )
                          }
                        />
                        {t("I reviewed the local reminder for")} {item.record.title}.
                      </label>
                      <button
                        type="button"
                        className={button}
                        disabled={busy || !checked.includes(item.record.id)}
                        onClick={() =>
                          void act(async () => {
                            const result = await request<unknown[]>("/notifications/local-reminder", {
                              method: "POST",
                              body: JSON.stringify({
                                record_id: item.record.id,
                                expected_version: item.record.version,
                                reviewed: true,
                              }),
                            });
                            setMessage({
                              key: "{value0} local mock reminder channel(s) recorded. No real messages sent.",
                              count: result.length,
                            });
                          })
                        }
                      >
                        {t("Queue local mock reminder")}
                      </button>
                    </>
                  )}
                </article>
              ))}
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className={button}
                  disabled={busy || workOffset === 0}
                  onClick={() => loadWork(Math.max(0, workOffset - 20))}
                >
                  {t("Previous care items")}
                </button>
                <button
                  type="button"
                  className={button}
                  disabled={busy || work.length < 20}
                  onClick={() => loadWork(workOffset + 20)}
                >
                  {t("More care items")}
                </button>
              </div>
            </>
          )}
        </section>
      )}
      {careRead && (
        <details className={panel}>
          <summary className="cursor-pointer font-semibold">
            {hi ? "स्थानीय अनुस्मारक और प्राथमिकताएं" : t("Local reminders, preferences & delivery history")}
          </summary>
          {isPatient && (
            <>
              <button
                type="button"
                className={button}
                disabled={busy}
                onClick={() =>
                  void act(async () => setPref(await request<Pref>("/notifications/preferences")))
                }
              >
                {t("Load reminder preferences")}
              </button>
              {pref && (
                <form
                  className="space-y-3"
                  aria-label={t("Local notification preferences")}
                  onSubmit={(event) => {
                    event.preventDefault();
                    void act(async () => {
                      setPref(
                        await request<Pref>("/notifications/preferences", {
                          method: "PUT",
                          body: JSON.stringify({
                            expected_version: pref.version,
                            enabled: pref.enabled,
                            channels: pref.channels,
                            language: pref.language,
                          }),
                        }),
                      );
                      setMessage("Local mock reminder preferences saved.");
                    });
                  }}
                >
                  <label className="flex gap-2">
                    <input
                      type="checkbox"
                      checked={pref.enabled}
                      onChange={(event) => setPref({ ...pref, enabled: event.target.checked })}
                    />
                    {t("Enable local mock reminders")}
                  </label>
                  <fieldset className="space-y-2">
                    <legend>{t("Mock channels (no external delivery)")}</legend>
                    {["in_app", "email", "sms", "whatsapp"].map((channel) => (
                      <label key={channel} className="flex gap-2">
                        <input
                          type="checkbox"
                          checked={pref.channels.includes(channel)}
                          onChange={(event) =>
                            setPref({
                              ...pref,
                              channels: event.target.checked
                                ? [...pref.channels, channel]
                                : pref.channels.filter((value) => value !== channel),
                            })
                          }
                        />
                        {t(human(channel))}
                      </label>
                    ))}
                  </fieldset>
                  <label className="block" htmlFor={`${formId}-reminder-language`}>
                    {t("Reminder language")}
                  </label>
                  <select
                    id={`${formId}-reminder-language`}
                    className={field}
                    value={pref.language}
                    onChange={(event) => setPref({ ...pref, language: event.target.value })}
                  >
                    {Object.entries(languages).map(([code, language]) => (
                      <option key={code} value={code} lang={code}>
                        {language.nativeName}
                      </option>
                    ))}
                  </select>
                  <button type="submit" className={button} disabled={busy || !pref.channels.length}>
                    {t("Save reminder preferences")}
                  </button>
                </form>
              )}
            </>
          )}
          <button type="button" className={button} disabled={busy} onClick={() => loadHistory()}>
            {t("View local delivery history")}
          </button>
          {deliveries && (
            <>
              {!deliveries.length && <p>{t("No local delivery attempts.")}</p>}
              {deliveries.map((row) => (
                <article className="rounded border p-3 text-sm" key={row.id}>
                  <p>
                    {t(human(row.channel))} · {row.mode} · {row.status}
                  </p>
                  <p>{row.body}</p>
                  {row.stale && (
                    <p className="text-amber-800">
                      {t("The linked care record has changed since this reminder.")}
                    </p>
                  )}
                </article>
              ))}
              <button
                type="button"
                className={button}
                disabled={busy || deliveryOffset === 0}
                onClick={() => loadHistory(Math.max(0, deliveryOffset - 20))}
              >
                {t("Previous delivery attempts")}
              </button>
              <button
                type="button"
                className={button}
                disabled={busy || deliveries.length < 20}
                onClick={() => loadHistory(deliveryOffset + 20)}
              >
                {t("Older delivery attempts")}
              </button>
            </>
          )}
        </details>
      )}
      <details className={panel}>
        <summary className="cursor-pointer font-semibold">{t("Source-linked medical overview")}</summary>
        <p className="text-sm">
          {t(
            "Exact structured source extracts and reported accounts. No generated clinical conclusions. Unrecorded allergies or diagnoses do not mean confirmed absence.",
          )}
        </p>
        <button type="button" className={button} disabled={busy} onClick={() => loadOverview()}>
          {t("Load source overview")}
        </button>
        {overview && (
          <>
            {overview.facts.map((fact, index) => (
              <article
                key={`${fact.source_id}-${index}`}
                className="space-y-2 break-words rounded border p-3 text-sm"
              >
                <h4 className="font-semibold">{fact.title}</h4>
                <p>
                  {t(human(fact.category))} · {fact.date} · {t(human(fact.provenance))}{" "}
                  {t("· Source version")} {fact.source_version}
                </p>
                {Object.entries(fact.details).map(([key, value]) => (
                  <p className="whitespace-pre-wrap" key={key}>
                    {t(human(key))}:{" "}
                    {value === null
                      ? t("Not recorded")
                      : typeof value === "object"
                        ? JSON.stringify(value)
                        : String(value)}
                  </p>
                ))}
                <button
                  type="button"
                  className={button}
                  disabled={busy}
                  onClick={() => void act(async () => setSource(await request(fact.source_path)))}
                >
                  {t("View source record:")} {fact.title}
                </button>
                {fact.documents.map((document) => (
                  <button
                    type="button"
                    key={document.id}
                    className={button}
                    disabled={busy}
                    onClick={() => void act(() => api.documents.download(document.id, document.file_name))}
                  >
                    {t("Download cited source:")} {document.title}
                  </button>
                ))}
              </article>
            ))}
            <p className="text-sm text-slate-500">{overview.missing_information}</p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={button}
                disabled={busy || overviewOffset === 0}
                onClick={() => loadOverview(Math.max(0, overviewOffset - 20))}
              >
                {t("Previous overview page")}
              </button>
              <button
                type="button"
                className={button}
                disabled={busy || !overview.has_more}
                onClick={() => loadOverview(overviewOffset + 20)}
              >
                {t("Next overview page")}
              </button>
            </div>
          </>
        )}
      </details>
      {readResources.includes("medications") && (
        <details className={panel}>
          <summary className="cursor-pointer font-semibold">{t("Medication comparison indicators")}</summary>
          <button
            type="button"
            className={button}
            disabled={busy}
            onClick={() =>
              void act(async () =>
                setReview(await request<Review>(`/clinical/medication-review?patient_id=${patientId}`)),
              )
            }
          >
            {t("Compare recorded medication sources")}
          </button>
          {review && (
            <>
              <p className="text-sm text-amber-900">
                {t("Clinical safety was not checked. Knowledge provider:")}{" "}
                {review.clinical_knowledge_provider}. {review.limitations}
              </p>
              {!review.allergy_records_included && (
                <p className="text-sm text-amber-900">
                  {t("Allergy records are outside the approved scope and are excluded from this comparison.")}
                </p>
              )}
              {review.approved_knowledge && review.approved_knowledge.status !== "not_configured" && (
                <section
                  aria-label={t("Knowledge release evidence")}
                  className="space-y-2 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm"
                >
                  <h4 className="font-semibold">{t("Knowledge release evidence")}</h4>
                  {review.approved_knowledge.status === "available" ? (
                    <>
                      <p>
                        {review.approved_knowledge.reference} · {review.approved_knowledge.release}
                      </p>
                      <p>
                        {t(
                          "Reviewed source mappings: {value0}. Excluded sources: {value1}. Assessed pairs: {value2}. Unassessed pairs: {value3}.",
                          {
                            value0: review.approved_knowledge.eligible_sources,
                            value1: review.approved_knowledge.excluded_sources,
                            value2: review.approved_knowledge.assessed_pairs,
                            value3: review.approved_knowledge.unassessed_pairs,
                          },
                        )}
                      </p>
                      {review.approved_knowledge.findings.map((finding, index) => (
                        <article
                          key={index}
                          className="space-y-1 rounded-lg border border-blue-100 bg-white p-3"
                        >
                          <p>{finding.message}</p>
                          <p className="text-xs text-slate-600">{finding.evidence_reference}</p>
                        </article>
                      ))}
                    </>
                  ) : (
                    <p>
                      {t(
                        "Knowledge release unavailable, changed or expired. No safety clearance is available.",
                      )}
                    </p>
                  )}
                  <p>
                    {t(
                      "These are evidence matches across recorded sources. Current use, timing, allergies and safe doses are not established. Missing pairs were not evaluated.",
                    )}
                  </p>
                </section>
              )}
              {review.truncated && (
                <p>{t("Result limit reached; review additional records in their source workspaces.")}</p>
              )}
              {!review.indicators.length && (
                <p>
                  {t(
                    "No literal comparison indicators in the loaded records. This is not a safety clearance.",
                  )}
                </p>
              )}
              {review.indicators.map((row, index) => (
                <article key={index} className="space-y-1 rounded border p-3 text-sm">
                  <p className="font-medium">{t(human(row.type))}</p>
                  <p>{row.message}</p>
                  {row.evidence_ids.map((id) => {
                    const evidence = review.evidence.find((item) => item.id === id);
                    return evidence ? (
                      <button
                        type="button"
                        className={button}
                        key={id}
                        disabled={busy}
                        onClick={() => void act(async () => setSource(await request(evidence.source_path)))}
                      >
                        {t("Evidence:")} {evidence.name} · {t(human(evidence.kind))} {t("· Version")}{" "}
                        {evidence.source_version}
                      </button>
                    ) : (
                      <p key={id}>
                        {t("Source record")} {id}
                      </p>
                    );
                  })}
                </article>
              ))}
              {!!review.synthetic_demonstrations.length && (
                <section
                  aria-label={t("Synthetic safety demonstrations")}
                  className="space-y-2 rounded border border-amber-300 bg-amber-50 p-3"
                >
                  <h4 className="font-semibold">{t("Synthetic software demonstrations only")}</h4>
                  {review.synthetic_demonstrations.map((row, index) => (
                    <p key={index}>
                      {row.message} {t("Evidence:")} {row.evidence}
                    </p>
                  ))}
                </section>
              )}
            </>
          )}
        </details>
      )}
      {careRead && readResources.includes("interventions") && (
        <details className={panel}>
          <summary className="cursor-pointer font-semibold">
            {t("Intervention events and observed outcomes")}
          </summary>
          <button type="button" className={button} disabled={busy} onClick={() => loadInterventions()}>
            {t("Load intervention event extract")}
          </button>
          {interventions && (
            <>
              <p className="text-sm">{interventions.limitations}</p>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">
                {JSON.stringify(
                  { groups: interventions.group_counts, events: interventions.events },
                  null,
                  2,
                )}
              </pre>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className={button}
                  onClick={() => saveJson(interventions, `intervention-events-${interventionOffset}.json`)}
                >
                  {t("Download observed event page")}
                </button>
                <button
                  type="button"
                  className={button}
                  disabled={busy || interventionOffset === 0}
                  onClick={() => loadInterventions(Math.max(0, interventionOffset - 50))}
                >
                  {t("Previous intervention page")}
                </button>
                <button
                  type="button"
                  className={button}
                  disabled={busy || !interventions.has_more}
                  onClick={() => loadInterventions(interventionOffset + 50)}
                >
                  {t("Next intervention page")}
                </button>
              </div>
            </>
          )}
        </details>
      )}
      {source !== null && (
        <section aria-label={t("Cited source record")} className={panel}>
          <h3 className="font-semibold">{t("Cited source record")}</h3>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs">
            {JSON.stringify(source, null, 2)}
          </pre>
          <button type="button" className={button} onClick={() => setSource(null)}>
            {t("Close cited source")}
          </button>
        </section>
      )}
      {fhirRead && (
        <details className={panel}>
          <summary className="cursor-pointer font-semibold">{t("FHIR R4 subset exchange")}</summary>
          <p className="text-sm">
            {t(
              "Exports structured records in a paged collection Bundle. Date-only appointments are care Tasks. Import supports explicit Patient/Condition/AllergyIntolerance/simple valueString Observation bundles only; no external references are fetched. Original JSON is retained. This is not ABDM access or conformance certification.",
            )}
          </p>
          <button type="button" className={button} disabled={busy} onClick={() => exportPage()}>
            {t("Export first FHIR page")}
          </button>
          {fhir && (
            <>
              <p>
                {fhir.entry.length - 1} {t("structured resources in downloaded page.")}
              </p>
              <button
                type="button"
                className={button}
                disabled={busy || !fhir.link?.length}
                onClick={() => exportPage(fhirOffset + 50)}
              >
                {t("Export next FHIR page")}
              </button>
            </>
          )}
          {fhirWrite && (
            <div className="space-y-3">
              <label className="block text-sm" htmlFor={`${formId}-fhir-json`}>
                {t("FHIR collection JSON")}
              </label>
              <textarea
                id={`${formId}-fhir-json`}
                className={field}
                rows={7}
                maxLength={1048576}
                value={rawBundle}
                onChange={(event) => {
                  setRawBundle(event.target.value);
                  setPreview(null);
                  setPreviewBody("");
                }}
              />
              <label className="block text-sm">
                {t("FHIR import review reason")}
                <input
                  className={field}
                  minLength={5}
                  maxLength={500}
                  value={reason}
                  onChange={(event) => {
                    setReason(event.target.value);
                    setPreview(null);
                  }}
                />
              </label>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={sourceChecked}
                  onChange={(event) => {
                    setSourceChecked(event.target.checked);
                    setPreview(null);
                  }}
                />
                {t("I checked this source bundle, its patient UUID and every assertion to import.")}
              </label>
              <button
                type="button"
                className={button}
                disabled={busy || !sourceChecked || reason.trim().length < 5 || !rawBundle.trim()}
                onClick={() =>
                  void act(async () => {
                    const body = JSON.stringify({
                      patient_id: patientId,
                      bundle: JSON.parse(rawBundle),
                      reason,
                      source_checked: sourceChecked,
                    });
                    setPreview(await request("/clinical/fhir/preview", { method: "POST", body }));
                    setPreviewBody(body);
                  })
                }
              >
                {t("Preview FHIR import")}
              </button>
              {preview && (
                <>
                  <p>{preview.warning}</p>
                  <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs">
                    {JSON.stringify(preview.records, null, 2)}
                  </pre>
                  <button
                    type="button"
                    className={button}
                    disabled={busy || !previewBody}
                    onClick={() =>
                      void act(async () => {
                        const result = await request<{ record_ids: string[] }>("/clinical/fhir/import", {
                          method: "POST",
                          body: previewBody,
                        });
                        setPreview(null);
                        setPreviewBody("");
                        setMessage({
                          key: "{value0} source assertions imported with original JSON retained. Refresh clinical records to view them.",
                          count: result.record_ids.length,
                        });
                      })
                    }
                  >
                    {t("Import reviewed source assertions")}
                  </button>
                </>
              )}
            </div>
          )}
        </details>
      )}
      <details className={panel}>
        <summary className="cursor-pointer font-semibold">{t("Synthetic risk model lab")}</summary>
        <p className="text-sm text-amber-900">
          {t(
            "Artificial data only. This model is not used to score this patient or select care. Feature contributions describe a fitted synthetic model, not causal effects.",
          )}
        </p>
        <button
          type="button"
          className={button}
          disabled={busy}
          onClick={() =>
            void act(async () => setEvaluation(await request<Evaluation>("/research/synthetic-risk")))
          }
        >
          {t("Load synthetic evaluation")}
        </button>
        {evaluation && (
          <>
            <p className="text-sm">
              {t(human(evaluation.model))} · {evaluation.version} {t("· Seed")} {evaluation.seed} ·{" "}
              {evaluation.test.count} {t("held-out artificial examples")}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr>
                    <th>{t("Held-out metric")}</th>
                    <th>{t("Logistic model")}</th>
                    <th>{t("Constant baseline")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    ["precision", "recall", "average_precision", "false_positive_rate", "brier"] as const
                  ).map((key) => (
                    <tr key={key}>
                      <td className="py-1">{t(human(key))}</td>
                      <td>{evaluation.test[key].toFixed(3)}</td>
                      <td>{evaluation.constant_baseline[key].toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details>
              <summary>{t("Cohorts, calibration and subgroup checks")}</summary>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">
                {JSON.stringify(
                  {
                    cohorts: evaluation.cohorts,
                    calibration: evaluation.test.calibration,
                    subgroups: evaluation.subgroups,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
            <form
              className="space-y-3"
              aria-label={t("Synthetic risk example")}
              onSubmit={(event) => {
                event.preventDefault();
                void act(async () =>
                  setCaseResult(
                    await request("/research/synthetic-risk", {
                      method: "POST",
                      body: JSON.stringify(caseValues),
                    }),
                  ),
                );
              }}
            >
              {Object.entries(caseValues).map(([key, value]) => (
                <label className="block text-sm" key={key}>
                  {t("Artificial")} {t(human(key))}
                  <input
                    className={field}
                    type="number"
                    required
                    min={["days_since_visit", "lead_days"].includes(key) ? 1 : 0}
                    max={key === "days_since_visit" ? 365 : key === "lead_days" ? 90 : 5}
                    value={value}
                    onChange={(event) =>
                      setCaseValues((previous) => ({ ...previous, [key]: Number(event.target.value) }))
                    }
                  />
                </label>
              ))}
              <button type="submit" className={button} disabled={busy}>
                {t("Evaluate artificial example")}
              </button>
            </form>
            {caseResult && (
              <div className="space-y-2 rounded border p-3 text-sm">
                <p>
                  {t("Synthetic probability:")} {(caseResult.synthetic_probability * 100).toFixed(1)}%
                </p>
                {Object.entries(caseResult.signed_log_odds_contributions).map(([key, value]) => (
                  <p key={key}>
                    {t(human(key))} {t("signed log-odds contribution:")} {value.toFixed(3)}
                  </p>
                ))}
              </div>
            )}
            <ul className="list-inside list-disc text-sm">
              {evaluation.limitations.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </>
        )}
      </details>
      <ResearchStudyPanel />
    </section>
  );
}
