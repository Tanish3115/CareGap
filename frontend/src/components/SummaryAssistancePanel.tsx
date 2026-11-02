"use client";

import { useLanguage } from "@/components/LanguageProvider";

import { useId, useState } from "react";
import { request, api } from "@/lib/api";
import { SourceData } from "./UnifiedTimeline";

type Status = { mode: string; reference: string; available: boolean; sends_source_data: boolean };
type Preference = {
  version: number;
  enabled: boolean;
  provider_reference: string;
  current_provider_reference: string;
};
type Fact = {
  category: string;
  title: string;
  date: string;
  provenance: string;
  source_version: number;
  source_path: string;
  details: Record<string, unknown>;
  documents: { id: string; title: string; file_name: string }[];
};
type Result = {
  mode: string;
  provider_reference: string;
  facts: Fact[];
  interpretations: unknown[];
  has_more: boolean;
  limitations: string;
};
const button =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50";

export function SummaryAssistancePanel({
  patientId,
  isPatient = false,
}: {
  patientId: string;
  isPatient?: boolean;
}) {
  const { t } = useLanguage();
  const id = useId();
  const [status, setStatus] = useState<Status | null>(null);
  const [pref, setPref] = useState<Preference | null>(null);
  const [checked, setChecked] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [offset, setOffset] = useState(0);
  const [source, setSource] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (error) {
      setResult(null);
      setSource(null);
      setError(error instanceof Error ? error.message : "Unable to load source assistance");
    } finally {
      setBusy(false);
    }
  }
  function load(start = 0) {
    void act(async () => {
      setResult(
        await request<Result>("/clinical/summary-assistance", {
          method: "POST",
          body: JSON.stringify({ patient_id: patientId, offset: start, limit: 10 }),
        }),
      );
      setOffset(start);
    });
  }
  return (
    <details
      className="min-w-0 space-y-3 rounded-2xl border bg-white p-5"
      aria-label={t("Source selection assistance")}
    >
      <summary className="cursor-pointer font-semibold">
        {t("Source selection assistance & processing consent")}
      </summary>
      <p className="text-sm text-slate-600">
        {t(
          "Assistance selects and orders exact authorized source extracts. It cannot add diagnoses, change treatment or introduce clinical statements. Original notes are treated as source data, not instructions for the processor.",
        )}
      </p>
      {error && (
        <p role="alert" className="text-red-700">
          {t(error)}
        </p>
      )}
      <button
        type="button"
        className={button}
        disabled={busy}
        onClick={() =>
          void act(async () => {
            setStatus(await request<Status>("/clinical/summary-assistance/status"));
            if (isPatient) {
              const value = await request<Preference>("/privacy/summary-processing");
              setPref(value);
              setChecked(false);
            }
          })
        }
      >
        {t("Load processing settings")}
      </button>
      {status && (
        <div className="space-y-3 text-sm">
          <p>
            {t("Processor:")} {status.reference} · {status.available ? t("Available") : t("Not configured")}
          </p>
          <p>
            {status.sends_source_data
              ? t(
                  "This configured processor receives authorized medical source extracts. Provider approval and the patient’s explicit opt-in are required. Consent to clinician sharing alone does not enable processing.",
                )
              : t("Local source extracts only. No model or external processor receives medical records.")}
          </p>
          {isPatient && pref && status.sends_source_data && (
            <form
              className="space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                void act(async () => {
                  setPref(
                    await request<Preference>("/privacy/summary-processing", {
                      method: "PUT",
                      body: JSON.stringify({
                        expected_version: pref.version,
                        enabled: checked,
                        provider_reference: status.reference,
                      }),
                    }),
                  );
                  setChecked(false);
                });
              }}
            >
              <p>
                {t("Stored processing preference:")} {pref.enabled ? t("Enabled") : t("Disabled")} ·{" "}
                {pref.provider_reference}
              </p>
              <label className="flex items-start gap-2" htmlFor={id}>
                <input
                  id={id}
                  type="checkbox"
                  checked={checked}
                  disabled={!status.available}
                  onChange={(event) => setChecked(event.target.checked)}
                />
                {t(
                  "I allow this named processor to receive authorized source extracts for requested summaries. I can disable future processing here; already processed data requires the provider’s retention procedure.",
                )}
              </label>
              <button type="submit" className={button} disabled={busy}>
                {t("Save processing preference")}
              </button>
            </form>
          )}
        </div>
      )}
      <button type="button" className={button} disabled={busy} onClick={() => load()}>
        {t("Request source assistance")}
      </button>
      {result && (
        <section className="space-y-3 text-sm" aria-label={t("Assisted source extracts")}>
          <p>
            {result.mode === "local_source_extracts"
              ? t("Local source extracts; no AI model used.")
              : t("Processor-selected source extracts; clinician review required.")}
          </p>
          <p>{result.limitations}</p>
          {!result.facts.length && (
            <p>
              {t(
                "No source extracts selected on this page. This does not establish absence of a condition or medicine.",
              )}
            </p>
          )}
          {result.facts.map((fact, index) => (
            <article className="space-y-2 break-words rounded border p-3" key={index}>
              <h4 className="font-semibold">{fact.title}</h4>
              <p>
                {t(fact.category.replaceAll("_", " "))} · {fact.date} ·{" "}
                {t(fact.provenance.replaceAll("_", " "))} {t("· Version")} {fact.source_version}
              </p>
              {Object.entries(fact.details).map(([key, value]) => (
                <p className="whitespace-pre-wrap" key={key}>
                  <span className="font-medium">{t(key.replaceAll("_", " "))}:</span>{" "}
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
                {t("View assisted source:")} {fact.title}
              </button>
              {fact.documents.map((doc) => (
                <button
                  type="button"
                  className={button}
                  disabled={busy}
                  key={doc.id}
                  onClick={() => void act(() => api.documents.download(doc.id, doc.file_name))}
                >
                  {t("Download assisted source:")} {doc.title}
                </button>
              ))}
            </article>
          ))}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={button}
              disabled={busy || offset === 0}
              onClick={() => load(Math.max(0, offset - 10))}
            >
              {t("Previous assisted sources")}
            </button>
            <button
              type="button"
              className={button}
              disabled={busy || !result.has_more}
              onClick={() => load(offset + 10)}
            >
              {t("More assisted sources")}
            </button>
          </div>
        </section>
      )}
      {source !== null && (
        <section aria-label={t("Assisted source record")} className="space-y-3 rounded border p-3">
          <h3 className="font-semibold">{t("Assisted source record")}</h3>
          <SourceData value={source} />
          <button type="button" className={button} onClick={() => setSource(null)}>
            {t("Close assisted source")}
          </button>
        </section>
      )}
    </details>
  );
}
