"use client";

import { useState } from "react";
import { request } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/utils";
import { useLanguage } from "./LanguageProvider";

type Receipt = {
  document_id: string;
  status: "pending" | "done";
  retry_required: boolean;
  created_at: string;
};
export function FileCleanupPanel() {
  const { t } = useLanguage();
  const [rows, setRows] = useState<Receipt[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() {
    setBusy(true);
    setError("");
    try {
      setRows(await request<Receipt[]>("/patient-file-deletions"));
    } catch (err) {
      setError(errorMessage(err, "Unable to load file cleanup status"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="rounded-xl border border-slate-200 bg-white p-4">
      <summary className="cursor-pointer text-sm font-semibold text-slate-800">
        {t("Deleted document file cleanup")}
      </summary>
      <p className="mt-3 text-sm text-slate-600">
        {t(
          "Latest 50 deletion receipts. Pending files are unavailable through the app while cleanup retries. Backups and provider-retained versions are outside this cleanup.",
        )}
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={() => void refresh()}
        className="my-3 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium disabled:opacity-50"
      >
        {t("Refresh file cleanup status")}
      </button>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {t(error)}
        </p>
      )}
      {rows && !rows.length && (
        <p className="text-sm text-slate-600">{t("No document deletion receipts.")}</p>
      )}
      <ul className="space-y-2">
        {rows?.map((row) => (
          <li key={row.document_id} className="rounded-lg bg-slate-50 p-3 text-sm">
            <span className="font-semibold">
              {t(row.status === "done" ? "File cleanup completed" : "Pending file cleanup")}
            </span>
            <span className="ml-2 text-slate-600">{formatDate(row.created_at)}</span>
            {row.retry_required && (
              <p className="mt-1 text-amber-800">
                {t("Cleanup will retry. If it remains pending, contact the operator.")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
