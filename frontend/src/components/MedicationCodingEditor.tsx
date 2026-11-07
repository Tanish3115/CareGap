"use client";

import { useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";
import { request } from "@/lib/api";

export type MedicationCoding = {
  system: string;
  code: string;
  display: string;
  release: string;
  evidence_reference: string;
  catalog_sha256: string;
  mode: "synthetic" | "approved_catalog";
  checked: boolean;
  uncertain: boolean;
};

export function MedicationCodingEditor({
  documentId,
  sourceReviewVersion,
  item,
  coding,
  onChange,
}: {
  documentId: string;
  sourceReviewVersion: number;
  item: unknown;
  coding: MedicationCoding | null;
  onChange: (coding: MedicationCoding | null) => void;
}) {
  const { t } = useLanguage();
  const [candidates, setCandidates] = useState<MedicationCoding[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function lookup() {
    setBusy(true);
    setError("");
    setCandidates(null);
    try {
      const response = await request<{ rows: { candidates: MedicationCoding[] }[] }>(
        `/documents/${documentId}/prescription/terminology`,
        {
          method: "POST",
          body: JSON.stringify({
            source_review_version: sourceReviewVersion,
            items: [{ ...(item as Record<string, unknown>), coding: null }],
          }),
        },
      );
      setCandidates(response.rows[0]?.candidates || []);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="space-y-2 rounded border border-slate-200 p-2"
      aria-label={t("Medication terminology")}
    >
      <h6 className="font-semibold">{t("Medication terminology")}</h6>
      <p>
        {t(
          "Catalog candidates require clinician review. Original medication text stays unchanged; this is not a safety check.",
        )}
      </p>
      <button
        type="button"
        className="rounded border px-2 py-1 disabled:opacity-50"
        disabled={busy}
        onClick={() => void lookup()}
      >
        {t("Find terminology candidates")}
      </button>
      {error && (
        <p role="alert" className="break-words text-red-700">
          {t(error)}
        </p>
      )}
      {candidates && !candidates.length && (
        <p role="status">
          {t("No terminology mapping is available. Keep the original name and seek clarification.")}
        </p>
      )}
      {candidates?.map((candidate) => (
        <button
          type="button"
          key={`${candidate.system}:${candidate.code}`}
          className="block w-full break-words rounded border p-2 text-left"
          onClick={() => {
            onChange({ ...candidate, checked: false, uncertain: true });
            setCandidates(null);
          }}
        >
          {candidate.display} · {candidate.code} · {candidate.release}
        </button>
      ))}
      {coding && (
        <div className="space-y-2 break-words">
          <p>
            {coding.display} · {coding.system} · {coding.code} · {coding.release}
          </p>
          <p>{coding.evidence_reference}</p>
          {coding.mode === "synthetic" && (
            <p className="text-amber-900">
              {t("Synthetic terminology fixture; not a real medication mapping.")}
            </p>
          )}
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={coding.checked && !coding.uncertain}
              onChange={(event) =>
                onChange({ ...coding, checked: event.target.checked, uncertain: !event.target.checked })
              }
            />
            {t("I reviewed this terminology mapping and its evidence.")}
          </label>
          <button
            type="button"
            className="rounded border px-2 py-1"
            onClick={() => {
              onChange(null);
              setCandidates(null);
            }}
          >
            {t("Remove terminology mapping")}
          </button>
        </div>
      )}
    </section>
  );
}
