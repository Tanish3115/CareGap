"use client";

import { useLanguage } from "@/components/LanguageProvider";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FileText,
  Pill,
  FlaskConical,
  ShieldCheck,
  Plus,
  Search,
  User,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import {
  WorkspaceNavigation,
  WorkspaceSection,
  QuickAction,
  patientDestinations,
} from "@/components/WorkspaceNavigation";
import { StatsCard } from "@/components/StatsCard";
import { DocumentCard } from "@/components/DocumentCard";
import { FileCleanupPanel } from "@/components/FileCleanupPanel";
import { DocumentUploadModal } from "@/components/DocumentUploadModal";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { CareWorkspace } from "@/components/CareWorkspace";
import { ClinicalWorkspace } from "@/components/ClinicalWorkspace";
import { MedicationUsePanel } from "@/components/MedicationUsePanel";
import { StructuredCarePanel } from "@/components/StructuredCarePanel";
import { CareInsightsPanel } from "@/components/CareInsightsPanel";
import { PrivacyPanel } from "@/components/OperationsPanel";
import { SummaryAssistancePanel } from "@/components/SummaryAssistancePanel";
import { UnifiedTimeline } from "@/components/UnifiedTimeline";
import type { MedicalDocument, PatientProfile, PatientStats } from "@/types";

export default function DashboardPage() {
  const { t } = useLanguage();
  const router = useRouter();
  const [section, setSection] = useState("overview");
  const [currentUser, setCurrentUser] = useState<Awaited<ReturnType<typeof api.auth.me>> | null>(null);
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
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Load user & patient profile
        const userRes = await api.auth.me();
        setCurrentUser(userRes);

        if (userRes.role === "patient") {
          const [profile, summaryStats, docs] = await Promise.all([
            api.patients.getProfile(),
            api.patients.getStats(),
            api.documents.list(),
          ]);

          if (profile) setPatientProfile(profile);
          if (summaryStats) setStats(summaryStats);
          setDocuments(docs);
          setFilteredDocuments(docs);
        } else {
          // Doctor or Admin
          setDocuments([]);
          setFilteredDocuments([]);
        }
      } catch (err) {
        const message = errorMessage(err, "Failed to load dashboard data");
        if (message === "Authentication required") router.replace("/login");
        else setError(message);
      } finally {
        setLoading(false);
      }
    };
    void fetchDashboardData();
  }, [router]);

  useEffect(() => {
    let result = documents;
    if (selectedType !== "all") {
      result = result.filter((d) => d.document_type === selectedType);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (d) => d.title.toLowerCase().includes(q) || d.file_name.toLowerCase().includes(q),
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
        newDoc.document_type === "prescription" ? prev.prescriptions_count + 1 : prev.prescriptions_count,
      lab_reports_count:
        newDoc.document_type === "lab_report" ? prev.lab_reports_count + 1 : prev.lab_reports_count,
    }));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col bg-slate-50">
        <Navbar user={currentUser} />
        <div className="flex-1 flex flex-col items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-3" />
          <p className="text-sm font-medium text-slate-600">
            {t("Loading your CareGap 360 Health Vault...")}
          </p>
        </div>
      </div>
    );
  }

  if (error)
    return (
      <div className="min-h-screen bg-slate-50">
        <Navbar user={currentUser} />
        <main className="mx-auto max-w-4xl p-8">
          <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
            {t(error)}
          </p>
          <button
            type="button"
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-white"
            onClick={() => window.location.reload()}
          >
            {t("Retry loading dashboard")}
          </button>
        </main>
      </div>
    );

  if (currentUser && currentUser.role !== "patient") {
    return (
      <div className="min-h-screen bg-slate-50">
        <Navbar user={currentUser} />
        <WorkspaceNavigation userRole={currentUser.role} section={section} onSection={setSection}>
          <CareWorkspace user={currentUser} section={section} />
        </WorkspaceNavigation>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Navbar user={currentUser} />

      <WorkspaceNavigation userRole="patient" section={section} onSection={setSection}>
        <div className="space-y-7">
          {/* Patient Profile Header */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-50 border border-blue-200 text-blue-700">
                <User className="h-7 w-7" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-bold text-slate-900">
                    {currentUser?.full_name || t("Patient Record")}
                  </h2>
                  <span className="hidden sm:inline-flex items-center space-x-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 border border-emerald-200">
                    <ShieldCheck className="h-3 w-3" />
                    <span>{t("Patient account")}</span>
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  {currentUser?.email} {currentUser?.phone && t("• {value0}", { value0: currentUser.phone })}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {patientProfile?.blood_group && (
                <div className="rounded-xl bg-slate-50 border border-slate-200 px-3 py-1.5 text-xs">
                  <span className="text-slate-500 font-medium">{t("Blood Group:")}</span>{" "}
                  <span className="font-bold text-slate-800">{patientProfile.blood_group}</span>
                </div>
              )}
              {patientProfile?.emergency_contact && (
                <div className="rounded-xl bg-slate-50 border border-slate-200 px-3 py-1.5 text-xs">
                  <span className="text-slate-500 font-medium">{t("Emergency:")}</span>{" "}
                  <span className="font-semibold text-slate-800">{patientProfile.emergency_contact}</span>
                </div>
              )}
              <button
                type="button"
                onClick={() => setIsUploadOpen(true)}
                className="inline-flex items-center space-x-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
              >
                <Plus className="h-4 w-4" />
                <span>{t("Upload Document")}</span>
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center space-x-2 rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">
              <AlertCircle className="h-5 w-5 shrink-0 text-red-600" />
              <span>{t(error)}</span>
            </div>
          )}

          {/* Clinical KPIs / Statistics */}
          <WorkspaceSection active={section} id="overview">
            <div className="space-y-7">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatsCard
                  title={t("Total Vault Documents")}
                  value={stats.total_documents}
                  description={t("Uploaded source documents")}
                  icon={FileText}
                  colorScheme="blue"
                />
                <StatsCard
                  title={t("Prescriptions")}
                  value={stats.prescriptions_count}
                  description={t("Stored clinical medication lists")}
                  icon={Pill}
                  colorScheme="emerald"
                />
                <StatsCard
                  title={t("Diagnostic Reports")}
                  value={stats.lab_reports_count}
                  description={t("Labs, pathology, and imaging")}
                  icon={FlaskConical}
                  colorScheme="amber"
                />
                <StatsCard
                  title={t("Doctor Consents")}
                  value={stats.active_doctor_grants}
                  description={t("Active clinician access grants")}
                  icon={ShieldCheck}
                  colorScheme="slate"
                />
              </div>

              <section aria-label={t("Quick actions")}>
                <h2 className="mb-4 text-lg font-semibold text-slate-900">{t("Quick actions")}</h2>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {patientDestinations
                    .filter((item) =>
                      ["documents", "consultations", "medications", "records", "care", "sharing"].includes(
                        item.id,
                      ),
                    )
                    .map((item) => (
                      <QuickAction key={item.id} destination={item} />
                    ))}
                </div>
              </section>
            </div>
          </WorkspaceSection>
          {currentUser?.patient?.id && (
            <>
              <WorkspaceSection active={section} id="consultations">
                <ClinicalWorkspace patientId={currentUser.patient.id} canDelete documents={documents} />
              </WorkspaceSection>
              <WorkspaceSection active={section} id="timeline">
                <UnifiedTimeline patientId={currentUser.patient.id} />
              </WorkspaceSection>
              <WorkspaceSection active={section} id="medications">
                <MedicationUsePanel patientId={currentUser.patient.id} isPatient />
              </WorkspaceSection>
              <WorkspaceSection active={section} id="records">
                <StructuredCarePanel patientId={currentUser.patient.id} documents={documents} />
              </WorkspaceSection>
              <WorkspaceSection active={section} id="care">
                <div className="space-y-6">
                  <SummaryAssistancePanel patientId={currentUser.patient.id} isPatient />
                  <CareInsightsPanel patientId={currentUser.patient.id} isPatient canWrite />
                </div>
              </WorkspaceSection>
              <WorkspaceSection active={section} id="privacy">
                <PrivacyPanel />
              </WorkspaceSection>
            </>
          )}

          {/* Document Repository & Filters */}
          <WorkspaceSection active={section} id="documents">
            <div className="mb-5">
              <FileCleanupPanel />
            </div>
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">{t("Medical Document Vault")}</h2>
                  <p className="text-xs text-slate-500">
                    {" "}
                    {t("Original documents with upload checksums; clinical contents require review")}{" "}
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
                      aria-label={t("Search records...")}
                      placeholder={t("Search records...")}
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
                    type="button"
                    key={tab.id}
                    onClick={() => setSelectedType(tab.id)}
                    aria-pressed={selectedType === tab.id}
                    className={`rounded-lg px-3 py-1.5 font-medium transition-colors whitespace-nowrap ${
                      selectedType === tab.id
                        ? "bg-blue-600 text-white shadow-sm"
                        : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                    }`}
                  >
                    {t(tab.label)}
                  </button>
                ))}
              </div>

              {/* Documents Grid or Empty State */}
              {filteredDocuments.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredDocuments.map((doc) => (
                    <DocumentCard key={doc.id} document={doc} canDelete />
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white p-12 text-center">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 mb-3">
                    <FileText className="h-6 w-6" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900">{t("No medical documents found")}</h3>
                  <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
                    {searchQuery || selectedType !== "all"
                      ? t("No records match your filter criteria. Try resetting the search or category.")
                      : t(
                          "Start building your longitudinal health record by securely uploading your first prescription or test report.",
                        )}
                  </p>
                  <div className="mt-5">
                    <button
                      type="button"
                      onClick={() => setIsUploadOpen(true)}
                      className="inline-flex items-center space-x-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      <span>{t("Upload Medical Record")}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </WorkspaceSection>
          {currentUser && (
            <div hidden={!["sharing", "profile"].includes(section)}>
              <CareWorkspace user={currentUser} section={section} />
            </div>
          )}
        </div>
      </WorkspaceNavigation>

      {/* Upload Modal */}
      <DocumentUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={(doc) => {
          handleUploadSuccess(doc);
          window.location.hash = "documents";
        }}
      />
    </div>
  );
}
