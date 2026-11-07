"use client";
import { useDetailNavigation } from "@/lib/useDetailNavigation";

import { useLanguage } from "@/components/LanguageProvider";

import { useState } from "react";
import { Download, FileText, Pill, FlaskConical, FileSearch, ShieldCheck, Loader2 } from "lucide-react";
import type { MedicalDocument, DocumentType } from "@/types";
import { formatBytes, formatDate } from "@/lib/utils";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { DocumentProcessingPanel } from "./DocumentProcessingPanel";
import { DeleteRecord } from "./DeleteRecord";

interface DocumentCardProps {
  document: MedicalDocument;
  canDelete?: boolean;
  initialProcessingOpen?: boolean;
}

export function DocumentCard({
  document,
  canDelete = false,
  initialProcessingOpen = false,
}: DocumentCardProps) {
  const { t } = useLanguage();
  const [downloading, setDownloading] = useState(false);
  const [processingOpen, setProcessingOpen] = useState(initialProcessingOpen);
  const detailNavigation = useDetailNavigation({ processingOpen });

  const getTypeIcon = (type: DocumentType) => {
    switch (type) {
      case "prescription":
        return <Pill className="h-5 w-5 text-indigo-600" />;
      case "lab_report":
        return <FlaskConical className="h-5 w-5 text-emerald-600" />;
      case "discharge_summary":
        return <FileSearch className="h-5 w-5 text-amber-600" />;
      default:
        return <FileText className="h-5 w-5 text-blue-600" />;
    }
  };

  const getTypeBadge = (type: DocumentType) => {
    switch (type) {
      case "prescription":
        return "bg-indigo-50 text-indigo-700 border-indigo-200";
      case "lab_report":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "discharge_summary":
        return "bg-amber-50 text-amber-700 border-amber-200";
      default:
        return "bg-slate-50 text-slate-700 border-slate-200";
    }
  };

  const handleDownload = async () => {
    try {
      setDownloading(true);
      await api.documents.download(document.id, document.file_name);
    } catch (err) {
      alert(t(errorMessage(err, "Failed to download medical document")));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div
      ref={detailNavigation}
      data-document-id={document.id}
      tabIndex={-1}
      style={{ scrollMarginTop: "7rem", gridColumn: processingOpen ? "1 / -1" : undefined }}
      className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-blue-200 hover:shadow-md transition-all"
    >
      <div>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 border border-slate-200">
              {getTypeIcon(document.document_type)}
            </div>
            <div className="min-w-0">
              <h4 className="break-words text-sm font-semibold leading-relaxed text-slate-900">
                {document.title}
              </h4>
              <p className="mt-1 break-all text-xs text-slate-500">{document.file_name}</p>
            </div>
          </div>
          <span
            className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium border capitalize ${getTypeBadge(
              document.document_type,
            )}`}
          >
            {t(document.document_type.replaceAll("_", " "))}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-500 border-t border-slate-100 pt-3">
          <div>
            <span className="font-medium text-slate-700">{t("Clinical Date:")}</span>{" "}
            {document.clinical_date ? formatDate(document.clinical_date) : t("Not recorded")}
          </div>
          <div className="text-right">
            <span className="font-medium text-slate-700">{t("Size:")}</span> {formatBytes(document.file_size)}
          </div>
        </div>

        <div className="mt-2.5 flex items-center space-x-1.5 text-[11px] text-slate-400 bg-slate-50 px-2 py-1 rounded font-mono truncate">
          <ShieldCheck className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          <span className="truncate" title={t("SHA-256: {value0}", { value0: document.sha256_hash })}>
            {" "}
            {t("SHA-256:")} {document.sha256_hash.substring(0, 16)}...
          </span>
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
        <span className="inline-flex items-center text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
          {document.status === "verified" ? t("Reviewed") : t("Uploaded · Unverified")}
        </span>

        <button
          type="button"
          onClick={handleDownload}
          disabled={downloading}
          className="inline-flex items-center space-x-1.5 rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-blue-600 hover:text-white transition-colors disabled:opacity-50"
        >
          {downloading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>{t("Fetching...")}</span>
            </>
          ) : (
            <>
              <Download className="h-3.5 w-3.5" />
              <span>{t("Download")}</span>
            </>
          )}
        </button>
      </div>
      <button
        type="button"
        className="mt-3 text-left text-xs font-semibold text-blue-700 underline"
        aria-expanded={processingOpen}
        onClick={() => setProcessingOpen((value) => !value)}
      >
        {processingOpen ? t("Hide processing") : t("Show processing")}
      </button>
      {processingOpen && (
        <div data-detail-target="processingOpen">
          <DocumentProcessingPanel
            documentId={document.id}
            filename={document.file_name}
            documentType={document.document_type}
          />
        </div>
      )}
      {canDelete && <DeleteRecord path={`/documents/${document.id}`} label="Delete document" document />}
    </div>
  );
}
