"use client";

import React, { useState, useRef, useEffect } from "react";
import { X, UploadCloud, FileCheck, AlertCircle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { DocumentType, MedicalDocument } from "@/types";

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
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [documentType, setDocumentType] = useState<DocumentType>("prescription");
  const [clinicalDate, setClinicalDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    if (allowedTypes?.length) setDocumentType(allowedTypes[0]);
    const previous = document.activeElement as HTMLElement | null;
    modalRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !loading) onClose();
      if (event.key !== "Tab") return;
      const elements = modalRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not([type="file"]), select');
      if (!elements?.length) return;
      const first = elements[0], last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", handler);
    return () => { document.removeEventListener("keydown", handler); previous?.focus(); };
  }, [isOpen, loading, onClose, allowedTypes]);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      if (!title) {
        setTitle(selected.name.replace(/\.[^/.]+$/, ""));
      }
      if (selected.size > 25 * 1024 * 1024) {
        setError("File exceeds the 25MB limit.");
        setFile(null);
        return;
      }
      setError(null);
    }
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
      setFile(null); setTitle(""); setClinicalDate("");
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to upload document. Please verify the file format and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div role="dialog" aria-modal="true" aria-label="Upload Medical Document" className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div ref={modalRef} className="relative w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl border border-slate-200 max-h-[90vh] overflow-y-auto">
        <button
          aria-label="Close upload"
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
            <h3 className="text-lg font-bold text-slate-900">Upload Medical Document</h3>
            <p className="text-xs text-slate-500">
              PDF and image content is validated. Downloads check the stored SHA-256 checksum.
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 flex items-center space-x-2 rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Document File (PDF, PNG, JPG - max 25MB)
            </label>
            <div className="mt-1 flex justify-center rounded-xl border-2 border-dashed border-slate-300 px-6 pt-5 pb-6 hover:border-blue-500 transition-colors bg-slate-50">
              <div className="text-center">
                {file ? (
                  <div className="flex flex-col items-center">
                    <FileCheck className="h-8 w-8 text-emerald-600 mb-2" />
                    <span className="text-sm font-medium text-slate-800">{file.name}</span>
                    <span className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</span>
                    <label className="mt-2 text-xs text-blue-600 hover:text-blue-700 cursor-pointer font-medium">
                      Choose a different file
                      <input
                        type="file"
                        className="sr-only"
                        accept=".pdf,.png,.jpg,.jpeg"
                        onChange={handleFileChange}
                      />
                    </label>
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    <UploadCloud className="h-8 w-8 text-slate-400 mb-2" />
                    <label className="relative cursor-pointer rounded-md font-semibold text-blue-600 hover:text-blue-700 focus-within:outline-none">
                      <span>Click to select file</span>
                      <input
                        type="file"
                        className="sr-only"
                        accept=".pdf,.png,.jpg,.jpeg"
                        onChange={handleFileChange}
                      />
                    </label>
                    <p className="text-xs text-slate-500 mt-1">Prescriptions, Lab Reports, Discharge Summaries</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Document Title
            </label>
            <input
              type="text"
              aria-label="Document Title"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Cardiology Visit Prescription"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Document Type
              </label>
              <select
                aria-label="Document Type"
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value as DocumentType)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none bg-white"
              >
                {(allowedTypes || ["prescription", "lab_report", "discharge_summary", "referral", "scan", "other"]).map(type => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Clinical Date (Optional)
              </label>
              <input
                type="date"
                aria-label="Clinical Date"
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
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !file}
              className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              <span>{loading ? "Vaulting..." : "Upload Document"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

