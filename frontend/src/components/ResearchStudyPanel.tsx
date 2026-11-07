"use client";
import { useDetailNavigation } from "@/lib/useDetailNavigation";

import { useState } from "react";
import { request } from "@/lib/api";
import { useLanguage } from "@/components/LanguageProvider";

export function ResearchStudyPanel() {
  const { t } = useLanguage();
  const [report, setReport] = useState<unknown>(null);
  const detailNavigation = useDetailNavigation({ report });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true);
    setError("");
    setReport(null);
    try {
      setReport(await request("/research/intervention-study"));
    } catch (error) {
      setError(error instanceof Error ? error.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <details ref={detailNavigation} className="space-y-3 rounded border p-3">
      <summary className="cursor-pointer font-semibold">
        {t("Registered synthetic intervention study")}
      </summary>
      <p className="text-sm text-amber-900">
        {t(
          "Artificial study units only. No patient was assigned an intervention. Estimates are research demonstrations, not clinical effects.",
        )}
      </p>
      <button
        type="button"
        className="rounded border px-3 py-2 text-sm disabled:opacity-50"
        disabled={busy}
        onClick={() => void load()}
      >
        {t("Load synthetic evaluation")}
      </button>
      {error && (
        <p role="alert" className="break-words text-red-700">
          {t(error)}
        </p>
      )}
      {report !== null && (
        <pre
          data-detail-target="report"
          className="max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs"
        >
          {JSON.stringify(report, null, 2)}
        </pre>
      )}
    </details>
  );
}
