"use client";
import { useDetailNavigation } from "@/lib/useDetailNavigation";

import { useLanguage } from "@/components/LanguageProvider";

import { useEffect, useId, useState } from "react";
import { api, request } from "@/lib/api";
import { PrescriptionPanel } from "./PrescriptionPanel";

type Review = {
  document_id: string;
  version: number;
  reviewed_text: string;
  source_text: string;
  reason: string;
  reviewer_name: string;
  reviewer_kind: "patient_reviewed" | "clinician_reviewed";
  created_at: string;
  source_sha256: string;
  processor_version: string;
  processing_attempt: number;
};
const button =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold disabled:opacity-50";

export function DocumentReviewPanel({
  documentId,
  filename,
  documentType,
  generatedText,
  attempt,
  canEdit,
  canViewPrescription,
  canEditPrescription,
}: {
  documentId: string;
  filename: string;
  documentType: string;
  generatedText: string;
  attempt: number;
  canEdit: boolean;
  canViewPrescription: boolean;
  canEditPrescription: boolean;
}) {
  const { t } = useLanguage();
  const formId = useId();
  const [review, setReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [reason, setReason] = useState("");
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [history, setHistory] = useState<Review[] | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const detailNavigation = useDetailNavigation({ editing, history });
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    request<Review | null>(`/documents/${documentId}/review`)
      .then((next) => {
        if (!cancelled) {
          setReview(next);
          setError("");
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setReview(null);
          setHistory(null);
          setEditing(false);
          setError(e.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, refresh]);

  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load or save the review");
    } finally {
      setBusy(false);
    }
  }
  function startReview() {
    setText(review?.reviewed_text ?? generatedText);
    setReason("");
    setChecked(false);
    setEditing(true);
    setMessage("");
  }
  function showHistory(offset: number) {
    void act(async () => {
      setHistory(
        await request<Review[]>(`/documents/${documentId}/review/history?limit=10&offset=${offset}`),
      );
      setHistoryOffset(offset);
    });
  }

  return (
    <section
      aria-label={t("Source transcription review")}
      ref={detailNavigation}
      className="space-y-3 border-t border-slate-200 pt-3"
    >
      <h5 className="font-semibold">{t("Transcription review")}</h5>
      <p className="text-xs text-slate-600">
        {t(
          "Check the original patient, date, names and numbers. Saving a transcription does not verify diagnoses, prescribing instructions or medication safety.",
        )}
      </p>
      {error && (
        <p role="alert" className="break-words text-xs text-red-700">
          {t(error)}
        </p>
      )}
      {message && (
        <p role="status" className="text-xs text-emerald-800">
          {t(message)}
        </p>
      )}
      {loading ? (
        <p className="text-xs text-slate-500">{t("Loading review…")}</p>
      ) : review ? (
        <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-3">
          <p className="text-xs font-medium">
            {review.reviewer_kind === "patient_reviewed"
              ? t("Patient-reviewed transcription")
              : t("Clinician-reviewed transcription")}{" "}
            {t("· Version")} {review.version} · {review.reviewer_name}
          </p>
          <p className="max-h-48 overflow-auto whitespace-pre-wrap break-words text-xs">
            {review.reviewed_text}
          </p>
          <p className="text-xs text-slate-500">
            {t("Reason:")} {review.reason}
          </p>
          {review.processing_attempt !== attempt && (
            <p className="text-xs text-amber-800">
              {t(
                "This review used an earlier processing attempt. Compare the new source text with the original before updating it.",
              )}
            </p>
          )}
        </div>
      ) : (
        <p className="text-xs text-slate-500">{t("No transcription review saved.")}</p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={button}
          disabled={busy}
          onClick={() => void act(() => api.documents.download(documentId, filename))}
        >
          {t("Download original for review")}
        </button>
        {canEdit && !loading && (
          <button type="button" className={button} disabled={busy} onClick={startReview}>
            {review ? t("Edit transcription review") : t("Review transcription")}
          </button>
        )}
        {review && (
          <button type="button" className={button} disabled={busy} onClick={() => showHistory(0)}>
            {t("Review history")}
          </button>
        )}
        <button
          type="button"
          className={button}
          disabled={busy}
          onClick={() => {
            setEditing(false);
            setHistory(null);
            setRefresh((value) => value + 1);
          }}
        >
          {t("Reload review")}
        </button>
      </div>
      {editing && canEdit && (
        <form
          aria-label={t("Edit source transcription")}
          data-detail-target="editing"
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void act(async () => {
              const next = await request<Review>(`/documents/${documentId}/review`, {
                method: "POST",
                body: JSON.stringify({
                  expected_version: review?.version || 0,
                  expected_attempt: attempt,
                  reviewed_text: text,
                  reason,
                  source_checked: checked,
                }),
              });
              setReview(next);
              setEditing(false);
              setHistory(null);
              setMessage("Transcription review saved. Original text and earlier reviews are preserved.");
            });
          }}
        >
          <fieldset disabled={busy} className="space-y-3">
            <div>
              <label htmlFor={`${formId}-text`} className="block text-xs font-medium">
                {t("Reviewed transcription")}
              </label>
              <textarea
                id={`${formId}-text`}
                rows={8}
                required
                maxLength={100000}
                value={text}
                onChange={(event) => setText(event.target.value)}
                className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-xs"
              />
            </div>
            <label className="block text-xs font-medium">
              {t("Reason for review")}
              <input
                required
                minLength={5}
                maxLength={500}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-xs"
              />
            </label>
            <label className="flex items-start gap-2 text-xs">
              <input
                type="checkbox"
                required
                checked={checked}
                onChange={(event) => setChecked(event.target.checked)}
                className="mt-0.5"
              />
              {t("I checked the original document and its patient/date association.")}
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
              >
                {t("Save transcription review")}
              </button>
              <button type="button" className={button} onClick={() => setEditing(false)}>
                {t("Cancel review")}
              </button>
            </div>
          </fieldset>
        </form>
      )}
      {history && (
        <section
          aria-label={t("Transcription review history")}
          data-detail-target="history"
          className="space-y-3"
        >
          <div className="flex flex-wrap gap-2">
            <h6 className="font-semibold">{t("Review history")}</h6>
            <button
              type="button"
              className="text-xs text-blue-700 underline"
              onClick={() => setHistory(null)}
            >
              {t("Close review history")}
            </button>
          </div>
          {history.map((item) => (
            <article
              className="space-y-1 rounded border border-slate-200 bg-white p-2 text-xs"
              key={item.version}
            >
              <p className="font-medium">
                {t("Version")} {item.version} · {item.reviewer_name} ·{" "}
                {item.reviewer_kind === "patient_reviewed" ? t("Patient-reviewed") : t("Clinician-reviewed")}
              </p>
              <p className="max-h-40 overflow-auto whitespace-pre-wrap break-words">{item.reviewed_text}</p>
              <p>
                {t("Reason:")} {item.reason}
              </p>
            </article>
          ))}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={button}
              disabled={busy || historyOffset === 0}
              onClick={() => showHistory(Math.max(0, historyOffset - 10))}
            >
              {t("Previous reviews")}
            </button>
            <button
              type="button"
              className={button}
              disabled={busy || history.length < 10}
              onClick={() => showHistory(historyOffset + 10)}
            >
              {t("Older reviews")}
            </button>
          </div>
        </section>
      )}
      {review && !loading && documentType === "prescription" && canViewPrescription && (
        <PrescriptionPanel
          documentId={documentId}
          sourceReviewVersion={review.version}
          sourceText={review.reviewed_text}
          canEdit={canEditPrescription}
        />
      )}
    </section>
  );
}
