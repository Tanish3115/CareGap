"use client";

import React, { useState } from "react";
import { Download, FileText, Pill, FlaskConical, FileSearch, ShieldCheck, Loader2 } from "lucide-react";
import { MedicalDocument, DocumentType } from "@/types";
import { formatBytes, formatDate } from "@/lib/utils";
import { api } from "@/lib/api";

interface DocumentCardProps {
  document: MedicalDocument;
}

export function DocumentCard({ document }: DocumentCardProps) {
  const [downloading, setDownloading] = useState(false);

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
    } catch (err: any) {
      alert(err.message || "Failed to download medical document");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:border-blue-200 hover:shadow-md transition-all">
      <div>
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 border border-slate-200">
              {getTypeIcon(document.document_type)}
            </div>
            <div>
              <h4 className="text-sm font-semibold text-slate-900 line-clamp-1">{document.title}</h4>
              <p className="text-xs text-slate-500">{document.file_name}</p>
            </div>
          </div>
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border capitalize ${getTypeBadge(
              document.document_type
            )}`}
          >
            {document.document_type.replace("_", " ")}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-500 border-t border-slate-100 pt-3">
          <div>
            <span className="font-medium text-slate-700">Clinical Date:</span>{" "}
            {formatDate(document.clinical_date || document.created_at)}
          </div>
          <div className="text-right">
            <span className="font-medium text-slate-700">Size:</span> {formatBytes(document.file_size)}
          </div>
        </div>

        <div className="mt-2.5 flex items-center space-x-1.5 text-[11px] text-slate-400 bg-slate-50 px-2 py-1 rounded font-mono truncate">
          <ShieldCheck className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          <span className="truncate" title={`SHA-256: ${document.sha256_hash}`}>
            SHA-256: {document.sha256_hash.substring(0, 16)}...
          </span>
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
        <span className="inline-flex items-center text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
          Securely Vaulted
        </span>

        <button
          onClick={handleDownload}
          disabled={downloading}
          className="inline-flex items-center space-x-1.5 rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-blue-600 hover:text-white transition-colors disabled:opacity-50"
        >
          {downloading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Fetching...</span>
            </>
          ) : (
            <>
              <Download className="h-3.5 w-3.5" />
              <span>Download</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

