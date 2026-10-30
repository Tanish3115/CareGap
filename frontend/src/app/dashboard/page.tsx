"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FileText,
  Pill,
  FlaskConical,
  ShieldCheck,
  Plus,
  Search,
  Filter,
  HeartPulse,
  User,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { StatsCard } from "@/components/StatsCard";
import { DocumentCard } from "@/components/DocumentCard";
import { DocumentUploadModal } from "@/components/DocumentUploadModal";
import { api } from "@/lib/api";
import { getAuthToken, getCachedUser } from "@/lib/auth";
import { MedicalDocument, PatientProfile, PatientStats } from "@/types";

export default function DashboardPage() {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [patientProfile, setPatientProfile] = useState<PatientProfile | null>(null);
  const [stats, setStats] = useState<PatientStats>({
    total_documents: 0,
    prescriptions_count: 0,
    lab_reports_count: 0,
    pending_care_gaps: 0,
    active_doctor_grants: 0,
  });
  const [documents, setDocuments] = useState<MedicalDocument[]>([]);
  const [filteredDocuments, setFilteredDocuments] = useState<MedicalDocument[]>([]);
  const [selectedType, setSelectedType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      router.push("/login");
      return;
    }

    const cached = getCachedUser();
    if (cached) {
      setCurrentUser(cached);
    }

    fetchDashboardData();
  }, [router]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load user & patient profile
      const userRes = await api.auth.me();
      setCurrentUser(userRes);

      if (userRes.role === "patient") {
        const [profile, summaryStats, docs] = await Promise.all([
          api.patients.getProfile().catch(() => null),
          api.patients.getStats().catch(() => ({
            total_documents: 0,
            prescriptions_count: 0,
            lab_reports_count: 0,
            pending_care_gaps: 0,
            active_doctor_grants: 0,
          })),
          api.documents.list(),
        ]);

        if (profile) setPatientProfile(profile);
        if (summaryStats) setStats(summaryStats);
        setDocuments(docs);
        setFilteredDocuments(docs);
      } else {
        // Doctor or Admin
        const docs = await api.documents.list();
        setDocuments(docs);
        setFilteredDocuments(docs);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let result = documents;
    if (selectedType !== "all") {
      result = result.filter((d) => d.document_type === selectedType);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (d) =>
          d.title.toLowerCase().includes(q) ||
          d.file_name.toLowerCase().includes(q)
      );
    }
    setFilteredDocuments(result);
  }, [selectedType, searchQuery, documents]);

  const handleUploadSuccess = (newDoc: MedicalDocument) => {
    setDocuments((prev) => [newDoc, ...prev]);
    setStats((prev) => ({
      ...prev,
      total_documents: prev.total_documents + 1,
      prescriptions_count:
        newDoc.document_type === "prescription"
          ? prev.prescriptions_count + 1
          : prev.prescriptions_count,
      lab_reports_count:
        newDoc.document_type === "lab_report"
          ? prev.lab_reports_count + 1
          : prev.lab_reports_count,
    }));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col bg-slate-50">
        <Navbar user={currentUser} />
        <div className="flex-1 flex flex-col items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-3" />
          <p className="text-sm font-medium text-slate-600">Loading your CareGap 360 Health Vault...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Navbar user={currentUser} />

      <main className="flex-1 mx-auto max-w-7xl w-full px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Patient Profile Header */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 border border-blue-200 text-blue-700">
              <User className="h-7 w-7" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-bold text-slate-900">
                  {currentUser?.full_name || "Patient Record"}
                </h1>
                <span className="inline-flex items-center space-x-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200">
                  <ShieldCheck className="h-3 w-3" />
                  <span>Verified Identity</span>
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {currentUser?.email} {currentUser?.phone && `• ${currentUser.phone}`}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {patientProfile?.blood_group && (
              <div className="rounded-xl bg-slate-50 border border-slate-200 px-3 py-1.5 text-xs">
                <span className="text-slate-500 font-medium">Blood Group:</span>{" "}
                <span className="font-bold text-slate-800">{patientProfile.blood_group}</span>
              </div>
            )}
            {patientProfile?.emergency_contact && (
              <div className="rounded-xl bg-slate-50 border border-slate-200 px-3 py-1.5 text-xs">
                <span className="text-slate-500 font-medium">Emergency:</span>{" "}
                <span className="font-semibold text-slate-800">{patientProfile.emergency_contact}</span>
              </div>
            )}
            <button
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center space-x-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>Upload Document</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center space-x-2 rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-600" />
            <span>{error}</span>
          </div>
        )}

        {/* Clinical KPIs / Statistics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatsCard
            title="Total Vault Documents"
            value={stats.total_documents}
            description="Verified longitudinal health records"
            icon={FileText}
            colorScheme="blue"
          />
          <StatsCard
            title="Prescriptions"
            value={stats.prescriptions_count}
            description="Stored clinical medication lists"
            icon={Pill}
            colorScheme="emerald"
          />
          <StatsCard
            title="Diagnostic Reports"
            value={stats.lab_reports_count}
            description="Labs, pathology, and imaging"
            icon={FlaskConical}
            colorScheme="amber"
          />
          <StatsCard
            title="Doctor Consents"
            value={stats.active_doctor_grants}
            description="Active clinician access grants"
            icon={ShieldCheck}
            colorScheme="slate"
          />
        </div>

        {/* Document Repository & Filters */}
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Medical Document Vault</h2>
              <p className="text-xs text-slate-500">
                Longitudinal record repository with verified provenance &amp; SHA-256 integrity
              </p>
            </div>

            <div className="flex items-center space-x-3">
              {/* Search */}
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search records..."
                  className="rounded-lg border border-slate-300 pl-9 pr-3 py-1.5 text-xs text-slate-900 focus:border-blue-500 outline-none bg-white w-48 sm:w-64"
                />
              </div>
            </div>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs">
            {[
              { id: "all", label: "All Records" },
              { id: "prescription", label: "Prescriptions" },
              { id: "lab_report", label: "Lab Reports" },
              { id: "discharge_summary", label: "Discharge Summaries" },
              { id: "referral", label: "Referrals" },
              { id: "scan", label: "Scans / Imaging" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSelectedType(tab.id)}
                className={`rounded-lg px-3 py-1.5 font-medium transition-colors whitespace-nowrap ${
                  selectedType === tab.id
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Documents Grid or Empty State */}
          {filteredDocuments.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredDocuments.map((doc) => (
                <DocumentCard key={doc.id} document={doc} />
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white p-12 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 mb-3">
                <FileText className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-semibold text-slate-900">No medical documents found</h3>
              <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
                {searchQuery || selectedType !== "all"
                  ? "No records match your filter criteria. Try resetting the search or category."
                  : "Start building your longitudinal health record by securely uploading your first prescription or test report."}
              </p>
              <div className="mt-5">
                <button
                  onClick={() => setIsUploadOpen(true)}
                  className="inline-flex items-center space-x-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Upload Medical Record</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Upload Modal */}
      <DocumentUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />
    </div>
  );
}

