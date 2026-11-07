"use client";
import { useDetailNavigation } from "@/lib/useDetailNavigation";

import { useState } from "react";
import { Trash2 } from "lucide-react";
import { request } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useLanguage } from "./LanguageProvider";

type Preview = { token: string; allowed: boolean; reason: string };
export function DeleteRecord({
  path,
  label,
  version,
  reviewVersion,
  document = false,
}: {
  path: string;
  label: string;
  version?: number;
  reviewVersion?: number;
  document?: boolean;
}) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const detailNavigation = useDetailNavigation({ open });
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  async function begin() {
    setOpen(true);
    setChecked(false);
    setError("");
    setPreview(null);
    if (!document) return;
    setBusy(true);
    try {
      setPreview(await request<Preview>(`${path}/deletion-preview`));
    } catch (err) {
      setError(errorMessage(err, "Unable to prepare deletion"));
    } finally {
      setBusy(false);
    }
  }
  async function remove(event: React.FormEvent) {
    event.preventDefault();
    if (!checked || busy || (document && !preview?.allowed)) return;
    setBusy(true);
    setError("");
    const query = document
      ? `expected_token=${encodeURIComponent(preview!.token)}`
      : `expected_version=${version}${reviewVersion === undefined ? "" : `&expected_review_version=${reviewVersion}`}`;
    try {
      await request(`${path}?${query}`, { method: "DELETE" });
      // Refresh all mounted source/review workspaces after an explicit destructive action.
      window.location.reload();
    } catch (err) {
      setError(errorMessage(err, "Unable to delete record"));
      setBusy(false);
    }
  }
  return (
    <div ref={detailNavigation} className="mt-3">
      {!open ? (
        <button
          type="button"
          onClick={() => void begin()}
          className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          {t(label)}
        </button>
      ) : (
        <form
          aria-label={t(label)}
          data-detail-target="open"
          onSubmit={remove}
          className="space-y-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-slate-800"
        >
          <h4 className="font-semibold text-red-800">{t(label)}</h4>
          <p>
            {t(
              document
                ? "The document and its extracted drafts and confirmed prescription entries will be removed. Linked clinical evidence must be reviewed first. Private file cleanup runs in the background; backups are not erased."
                : "Deletion removes this record and its related history. Original uploads, retained import bundles, audit metadata and backups are not erased by this action.",
            )}
          </p>
          <p>{t("Other open record views will refresh. Save any drafts before deleting.")}</p>
          {preview && !preview.allowed && <p role="alert">{t(preview.reason)}</p>}
          {error && (
            <p role="alert" className="text-red-800">
              {t(error)}
            </p>
          )}
          <fieldset disabled={busy || (document && !preview?.allowed)} className="space-y-3">
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                required
                checked={checked}
                onChange={(event) => setChecked(event.target.checked)}
              />
              {t("I understand this deletion cannot be undone.")}
            </label>
            <button
              type="submit"
              disabled={!checked}
              className="rounded-lg bg-red-700 px-4 py-2 font-semibold text-white disabled:opacity-50"
            >
              {t("Delete permanently")}
            </button>
          </fieldset>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setOpen(false);
              setChecked(false);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-medium"
          >
            {t("Cancel deletion")}
          </button>
          {document && !busy && (
            <button
              type="button"
              onClick={() => void begin()}
              className="ml-3 rounded-lg border border-slate-300 bg-white px-3 py-2 font-medium"
            >
              {t("Refresh deletion check")}
            </button>
          )}
        </form>
      )}
    </div>
  );
}
