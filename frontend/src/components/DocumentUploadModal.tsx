"use client";

import { useLanguage } from "@/components/LanguageProvider";

import type React from "react";
import { useId, useState, useRef, useEffect } from "react";
import { X, UploadCloud, FileCheck, AlertCircle, Loader2 } from "lucide-react";
import Image from "next/image";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { DocumentType, MedicalDocument } from "@/types";

interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (newDoc: MedicalDocument) => void;
  patientId?: string;
  allowedTypes?: DocumentType[];
}

export function DocumentUploadModal({
  isOpen,
  onClose,
  onUploadSuccess,
  patientId,
  allowedTypes,
}: DocumentUploadModalProps) {
  const { t } = useLanguage();
  const formId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [documentType, setDocumentType] = useState<DocumentType>("prescription");
  const [clinicalDate, setClinicalDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const closeHandler = useRef(onClose);
  const busy = useRef(loading);
  useEffect(() => {
    closeHandler.current = onClose;
    busy.current = loading;
  }, [onClose, loading]);
  useEffect(() => {
    if (!file || !isOpen) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file, isOpen]);

  useEffect(() => {
    if (isOpen && allowedTypes?.length) setDocumentType(allowedTypes[0]);
  }, [isOpen, allowedTypes]);

  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    modalRef.current?.querySelector<HTMLButtonElement>("[data-upload-picker]")?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy.current) closeHandler.current();
      if (event.key !== "Tab") return;
      const elements = Array.from(
        modalRef.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not([type="file"]):not(:disabled), select:not(:disabled)',
        ) || [],
      ).filter((element) => element.getClientRects().length > 0);
      if (!elements?.length) return;
      const first = elements[0],
        last = elements[elements.length - 1];
      if (!elements.includes(document.activeElement as HTMLElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
        return;
      }
      if (
        event.shiftKey &&
        (document.activeElement === first || !modalRef.current?.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last || !modalRef.current?.contains(document.activeElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const selectFile = (selected: File) => {
    if (loading) return;
    if (
      !/\.(pdf|png|jpe?g)$/i.test(selected.name) ||
      (selected.type && !["application/pdf", "image/png", "image/jpeg"].includes(selected.type))
    ) {
      setFile(null);
      setError("Choose a PDF, PNG or JPG file.");
      return;
    }
    if (selected.size > 25 * 1024 * 1024) {
      setFile(null);
      setError("File exceeds the 25MB limit.");
      return;
    }
    setFile(selected);
    if (!title) {
      setTitle(selected.name.replace(/\.[^/.]+$/, ""));
    }
    setError(null);
  };
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) selectFile(selected);
    e.target.value = "";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a medical document to upload.");
      return;
    }
    if (!title.trim()) {
      setError("Please enter a document title.");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", title.trim());
      formData.append("document_type", documentType);
      if (patientId) formData.append("patient_id", patientId);
      if (clinicalDate) {
        formData.append("clinical_date", clinicalDate);
      }

      const res = await api.documents.upload(formData);
      onUploadSuccess(res.document);
      setFile(null);
      setTitle("");
      setClinicalDate("");
      onClose();
    } catch (err) {
      setError(errorMessage(err, "Failed to upload document. Please verify the file format and try again."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("Upload Medical Document")}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4"
    >
      <div
        ref={modalRef}
        className="upload-dialog relative w-full max-w-lg rounded-2xl bg-white p-5 sm:p-7 shadow-xl border border-slate-200 max-h-[90vh] overflow-y-auto"
      >
        <button
          type="button"
          aria-label={t("Close upload")}
          disabled={loading}
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex items-center space-x-3 mb-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 border border-blue-200 text-blue-600">
            <UploadCloud className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">{t("Upload Medical Document")}</h3>
            <p className="text-xs text-slate-500"> {t("Prescriptions, Lab Reports, Discharge Summaries")} </p>
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="mb-4 flex items-center space-x-2 rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200"
          >
            <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />
            <span>{t(error)}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} aria-busy={loading} className="space-y-4">
          <ol
            aria-label={t("Upload steps")}
            className="mb-5 grid grid-cols-3 gap-2 text-center text-xs font-semibold"
          >
            <li className="rounded-lg bg-blue-50 px-2 py-3 text-blue-900">1 · {t("Select file")}</li>
            <li
              className={`rounded-lg px-2 py-3 ${file ? "bg-blue-50 text-blue-900" : "bg-slate-50 text-slate-600"}`}
            >
              2 · {t("Check details")}
            </li>
            <li
              className={`rounded-lg px-2 py-3 ${loading ? "bg-blue-50 text-blue-900" : "bg-slate-50 text-slate-600"}`}
            >
              3 · {t("Upload")}
            </li>
          </ol>
          <div>
            <label htmlFor={`${formId}-field-1`} className="block text-xs font-semibold text-slate-700 mb-1">
              {" "}
              {t("Document File (PDF, PNG, JPG - max 25MB)")}{" "}
            </label>
            <fieldset
              aria-label={t("Select file")}
              className="upload-dropzone mt-1 flex justify-center"
              data-dragging={dragging}
              onDragOver={(event) => {
                event.preventDefault();
                if (!loading) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                if (event.dataTransfer.files.length !== 1) {
                  setError("Choose one document at a time.");
                  return;
                }
                selectFile(event.dataTransfer.files[0]);
              }}
            >
              <div className="text-center">
                {file ? (
                  <div className="flex flex-col items-center">
                    <FileCheck className="h-8 w-8 text-emerald-600 mb-2" />
                    {previewUrl && file.type.startsWith("image/") && (
                      <Image
                        src={previewUrl}
                        alt={t("Selected document preview")}
                        width={320}
                        height={180}
                        unoptimized
                        className="mb-3 max-h-44 w-auto rounded-lg object-contain"
                      />
                    )}
                    <span className="text-sm font-medium text-slate-800">{file.name}</span>
                    <span className="text-xs text-slate-500">
                      {(file.size / 1024).toFixed(1)} {t("KB")}
                    </span>
                    {previewUrl && (
                      <a
                        href={previewUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 text-sm font-medium text-blue-700 underline"
                      >
                        {t("Preview selected file")}
                      </a>
                    )}
                    <div className="mt-2 text-sm text-blue-600 font-medium">
                      {" "}
                      <button
                        data-upload-picker
                        type="button"
                        disabled={loading}
                        onClick={() => fileInput.current?.click()}
                        className="min-h-11 underline"
                      >
                        {t("Choose a different file")}
                      </button>
                      <input
                        ref={fileInput}
                        id={`${formId}-field-1`}
                        type="file"
                        className="sr-only"
                        tabIndex={-1}
                        accept=".pdf,.png,.jpg,.jpeg"
                        onChange={handleFileChange}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    <UploadCloud className="h-8 w-8 text-slate-400 mb-2" />
                    <div className="relative rounded-md font-semibold text-blue-600">
                      <button
                        data-upload-picker
                        type="button"
                        disabled={loading}
                        onClick={() => fileInput.current?.click()}
                        className="min-h-11 rounded-lg border border-blue-200 bg-white px-4"
                      >
                        {t("Click to select file")}
                      </button>
                      <input
                        ref={fileInput}
                        id={`${formId}-field-1`}
                        type="file"
                        className="sr-only"
                        tabIndex={-1}
                        accept=".pdf,.png,.jpg,.jpeg"
                        onChange={handleFileChange}
                      />
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{t("Or drag one document here")}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {t("Prescriptions, Lab Reports, Discharge Summaries")}
                    </p>
                  </div>
                )}
              </div>
            </fieldset>
          </div>
          <p className="rounded-xl bg-blue-50 p-3 text-sm leading-relaxed text-blue-900">
            {t("Your original is saved first. Extracted information stays unverified until reviewed.")}
          </p>
          {loading && (
            <p role="status" className="text-sm text-blue-800">
              {t("Uploading your document. Please keep this window open.")}
            </p>
          )}

          <div>
            <label htmlFor={`${formId}-field-2`} className="block text-xs font-semibold text-slate-700 mb-1">
              {" "}
              {t("Document Title")}{" "}
            </label>
            <input
              id={`${formId}-field-2`}
              type="text"
              aria-label={t("Document Title")}
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("e.g. Cardiology Visit Prescription")}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor={`${formId}-field-3`}
                className="block text-xs font-semibold text-slate-700 mb-1"
              >
                {" "}
                {t("Document Type")}{" "}
              </label>
              <select
                id={`${formId}-field-3`}
                aria-label={t("Document Type")}
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value as DocumentType)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none bg-white"
              >
                {(
                  allowedTypes || [
                    "prescription",
                    "lab_report",
                    "discharge_summary",
                    "referral",
                    "scan",
                    "other",
                  ]
                ).map((type) => (
                  <option key={type} value={type}>
                    {t(type.replaceAll("_", " "))}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor={`${formId}-field-4`}
                className="block text-xs font-semibold text-slate-700 mb-1"
              >
                {" "}
                {t("Clinical Date (Optional)")}{" "}
              </label>
              <input
                id={`${formId}-field-4`}
                type="date"
                aria-label={t("Clinical Date")}
                value={clinicalDate}
                onChange={(e) => setClinicalDate(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>

          <div className="mt-6 flex justify-end space-x-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
            >
              {" "}
              {t("Cancel")}{" "}
            </button>
            <button
              type="submit"
              disabled={loading || !file}
              className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              <span>{loading ? t("Vaulting...") : t("Upload Document")}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
