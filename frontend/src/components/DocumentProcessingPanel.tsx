"use client";

import { useLanguage } from "@/components/LanguageProvider";

import { useEffect, useId, useState } from "react";
import { request } from "@/lib/api";
import { DocumentReviewPanel } from "./DocumentReviewPanel";

type ProcessingJob = {
  status: "not_queued" | "queued" | "processing" | "succeeded" | "failed";
  attempts: number;
  max_attempts: number;
  can_retry: boolean;
  error_code: string | null;
  can_view_review: boolean;
  can_review: boolean;
  can_reprocess: boolean;
  can_view_prescription: boolean;
  can_edit_prescription: boolean;
  result: {
    kind: "pdf_text" | "image";
    text: string;
    page_count: number;
    needs_ocr: boolean;
    truncated: boolean;
    verification_status: "unverified";
    source_sha256: string;
    pages: {
      page_number: number;
      method: string;
      confidence: number | null;
      warning: string | null;
      words: { text: string; confidence: number }[];
    }[];
  } | null;
};
const statusLabel = {
  not_queued: "Not requested",
  queued: "Queued",
  processing: "Processing",
  succeeded: "Completed",
  failed: "Failed",
};

export function DocumentProcessingPanel({
  documentId,
  filename,
  documentType,
}: {
  documentId: string;
  filename: string;
  documentType: string;
}) {
  const { t } = useLanguage();
  const textId = useId();
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const next = await request<ProcessingJob>(`/documents/${documentId}/processing`);
        if (cancelled) return;
        setJob(next);
        setError("");
        if (next.status === "queued" || next.status === "processing")
          timer = setTimeout(() => void load(), 2000);
      } catch (e) {
        if (!cancelled) {
          setJob(null);
          setError(e instanceof Error ? e.message : "Unable to load processing status");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [documentId, refresh]);

  async function retry() {
    setBusy(true);
    setError("");
    try {
      setJob(await request<ProcessingJob>(`/documents/${documentId}/processing/retry`, { method: "POST" }));
      setRefresh((value) => value + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to request processing");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-label={t("Document processing")}
      className="mt-4 space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm"
    >
      <h5 className="font-semibold text-slate-900">{t("Source processing")}</h5>
      {error && (
        <p role="alert" className="break-words text-red-700">
          {t(error)}
        </p>
      )}
      {job ? (
        <>
          <p className="font-medium">
            {t("Status:")} {statusLabel[job.status]}
          </p>
          <p className="text-xs text-slate-500">
            {t("Attempts:")} {job.attempts} / {job.max_attempts}
            {t(". Original documents are preserved.")}
          </p>
          {job.status === "queued" && (
            <p className="text-xs text-slate-600">
              {t("Waiting for the document worker. Status updates automatically while this panel is open.")}
            </p>
          )}
          {job.status === "processing" && (
            <p className="text-xs text-slate-600">
              {t("Checking the original source and reading available PDF text.")}
            </p>
          )}
          {job.status === "failed" && (
            <p className="text-xs text-red-700">
              {job.error_code === "timeout"
                ? t("Processing exceeded the time limit.")
                : job.error_code === "lease_exhausted"
                  ? t("The worker stopped repeatedly before completion.")
                  : t("Source processing failed.")}{" "}
              {job.can_retry
                ? t("You can retry after checking the original file.")
                : t("The attempt limit was reached.")}
            </p>
          )}
          {job.result && (
            <>
              <p className="text-xs text-slate-600">
                {job.result.page_count} {t("page(s) · Unverified source content")}
              </p>
              {job.result.needs_ocr && (
                <p className="text-xs text-amber-800">
                  {t("Some pages still need readable text. Check the original before transcribing.")}
                </p>
              )}
              {job.result.truncated && (
                <p className="text-xs text-amber-800">
                  {t("Text was truncated at the processing limit. Refer to the original document.")}
                </p>
              )}
              {job.result.text && (
                <div>
                  <label className="block text-xs font-medium" htmlFor={textId}>
                    {t("Unverified source text")}
                  </label>
                  <textarea
                    id={textId}
                    readOnly
                    rows={6}
                    value={job.result.text}
                    className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-xs"
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    {t("This text has not been converted into verified diagnoses or medication records.")}
                  </p>
                </div>
              )}
              {(job.result.pages || []).map((page) => (
                <details
                  key={page.page_number}
                  className="rounded border border-slate-200 bg-white p-2 text-xs"
                >
                  <summary className="cursor-pointer font-medium">
                    {t("Page")} {page.page_number} ·{" "}
                    {page.method === "tesseract"
                      ? t("Local OCR")
                      : page.method === "pdf_text"
                        ? t("PDF text")
                        : t("Needs transcription")}
                    {page.confidence !== null
                      ? t(" · Engine confidence {value0}%", { value0: Math.round(page.confidence) })
                      : ""}
                  </summary>
                  <p className="mt-2 text-slate-500">
                    {t(
                      "OCR confidence is not clinical certainty. Check every clinical value against the original.",
                    )}
                  </p>
                  {page.warning && <p className="mt-1 text-amber-800">{page.warning.replaceAll("_", " ")}</p>}
                  {page.words?.some((word) => word.confidence < 80) && (
                    <p className="mt-1 break-words text-amber-800">
                      {t("Low-confidence words:")}{" "}
                      {page.words
                        .filter((word) => word.confidence < 80)
                        .slice(0, 40)
                        .map((word) => `${word.text} (${Math.round(word.confidence)}%)`)
                        .join(", ")}
                    </p>
                  )}
                </details>
              ))}
              {job.can_view_review ? (
                <DocumentReviewPanel
                  documentId={documentId}
                  filename={filename}
                  documentType={documentType}
                  generatedText={job.result.text}
                  attempt={job.attempts}
                  canEdit={job.can_review}
                  canViewPrescription={job.can_view_prescription}
                  canEditPrescription={job.can_edit_prescription}
                />
              ) : (
                <p className="text-xs text-slate-500">
                  {t("Reviewed transcriptions require patient-approved clinical access.")}
                </p>
              )}
            </>
          )}
          {(job.can_retry || job.can_reprocess) && (
            <button
              type="button"
              disabled={busy}
              className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
              onClick={() => void retry()}
            >
              {busy
                ? t("Requesting…")
                : job.status === "not_queued"
                  ? t("Process document")
                  : job.can_reprocess
                    ? t("Run updated OCR")
                    : t("Retry processing")}
            </button>
          )}
        </>
      ) : (
        !error && <p className="text-xs text-slate-500">{t("Loading processing status…")}</p>
      )}
      <button
        type="button"
        className="block text-xs font-medium text-blue-700 underline disabled:opacity-50"
        disabled={busy}
        onClick={() => setRefresh((value) => value + 1)}
      >
        {t("Refresh processing status")}
      </button>
    </section>
  );
}
