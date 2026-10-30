import React from "react";
import Link from "next/link";
import {
  Activity,
  ShieldCheck,
  FileCheck2,
  GitCompare,
  TrendingUp,
  Lock,
  ArrowRight,
  UserCheck,
  Stethoscope,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Navbar />

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-white border-b border-slate-200 py-16 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="lg:grid lg:grid-cols-12 lg:gap-12 items-center">
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center space-x-2 rounded-full bg-blue-50 border border-blue-200 px-3.5 py-1 text-xs font-semibold text-blue-700">
                <ShieldCheck className="h-4 w-4" />
                <span>Patient-Controlled Zero-Trust Architecture</span>
              </div>

              <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-slate-900 leading-[1.15]">
                Intelligent Longitudinal Health Records & Care Continuity
              </h1>

              <p className="text-lg text-slate-600 leading-relaxed max-w-2xl">
                CareGap 360 unifies scattered medical visits, prescriptions, and lab reports into a single,
                patient-owned timeline. Prevent medication discrepancies, eliminate forgotten follow-ups,
                and share records with doctors through audited, time-limited consent.
              </p>

              <div className="flex flex-col sm:flex-row gap-3 pt-2">
                <Link
                  href="/register"
                  className="inline-flex items-center justify-center space-x-2 rounded-xl bg-blue-600 px-6 py-3.5 text-base font-semibold text-white shadow-md hover:bg-blue-700 transition-all"
                >
                  <span>Create Patient Account</span>
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="/login"
                  className="inline-flex items-center justify-center space-x-2 rounded-xl border border-slate-300 bg-white px-6 py-3.5 text-base font-semibold text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
                >
                  <Stethoscope className="h-4 w-4 text-slate-500" />
                  <span>Clinician / Doctor Portal</span>
                </Link>
              </div>

              <div className="pt-4 grid grid-cols-3 gap-4 border-t border-slate-100 text-xs text-slate-500">
                <div className="flex items-center space-x-1.5">
                  <Lock className="h-4 w-4 text-emerald-600 shrink-0" />
                  <span>SHA-256 Provenance</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <UserCheck className="h-4 w-4 text-blue-600 shrink-0" />
                  <span>Patient-Governed Consent</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <Activity className="h-4 w-4 text-indigo-600 shrink-0" />
                  <span>FHIR-Aligned Schema</span>
                </div>
              </div>
            </div>

            {/* Visual Feature Card Preview */}
            <div className="mt-10 lg:mt-0 lg:col-span-5">
              <div className="rounded-2xl border border-slate-200 bg-slate-900 p-6 shadow-2xl text-white">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div className="flex items-center space-x-2">
                    <div className="h-3 w-3 rounded-full bg-red-500" />
                    <div className="h-3 w-3 rounded-full bg-amber-500" />
                    <div className="h-3 w-3 rounded-full bg-emerald-500" />
                  </div>
                  <span className="text-xs font-mono text-slate-400">CareGap 360 Vault v0.1</span>
                </div>

                <div className="mt-6 space-y-4">
                  <div className="rounded-lg bg-slate-800/80 p-4 border border-slate-700">
                    <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                      <span>Document Ingestion Pipeline</span>
                      <span className="text-emerald-400 font-semibold">Active</span>
                    </div>
                    <p className="text-sm font-medium text-slate-200">
                      Cardiology Consultation &amp; Prescription.pdf
                    </p>
                    <div className="mt-2 text-xs font-mono text-slate-500 truncate">
                      SHA: e2b4f910a394c8e7... Verified
                    </div>
                  </div>

                  <div className="rounded-lg bg-slate-800/80 p-4 border border-slate-700">
                    <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                      <span>Zero-Trust Consent Grant</span>
                      <span className="text-blue-400 font-semibold">Time-Limited</span>
                    </div>
                    <p className="text-sm font-medium text-slate-200">
                      Dr. Gregory House — Princeton-Plainsboro
                    </p>
                    <div className="mt-2 text-xs text-slate-400">
                      Scope: <span className="text-slate-300">Prescriptions &amp; Labs</span> | Expires: 24h
                    </div>
                  </div>

                  <div className="rounded-lg bg-blue-950/60 p-4 border border-blue-800/60">
                    <div className="flex items-center space-x-2 text-blue-400 text-xs font-semibold mb-1">
                      <GitCompare className="h-4 w-4" />
                      <span>Longitudinal Reconciliation Engine</span>
                    </div>
                    <p className="text-xs text-slate-300">
                      Tracks duplicate medication entries and conflicting treatment regimens across independent visits.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Core Architectural Pillars */}
      <section className="py-16 bg-slate-50">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <h2 className="text-xs font-bold uppercase tracking-widest text-blue-600">Enterprise Engineering</h2>
            <p className="mt-2 text-3xl font-extrabold text-slate-900 tracking-tight">
              Built for Real-World Healthcare Complexity
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 mb-4">
                <FileCheck2 className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">Unified Medical Vault</h3>
              <p className="mt-2 text-sm text-slate-600 leading-relaxed">
                Securely upload and retain PDFs, scans, and lab reports with non-repudiation SHA-256 hashing.
                Original clinical sources are preserved immutably.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 mb-4">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">Zero-Trust Consent</h3>
              <p className="mt-2 text-sm text-slate-600 leading-relaxed">
                Doctors cannot query patient data by name. Access is granted strictly via explicit patient approval,
                scoped by document type and automatically expired.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 mb-4">
                <TrendingUp className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">Care Continuity Analytics</h3>
              <p className="mt-2 text-sm text-slate-600 leading-relaxed">
                Identify incomplete care journeys and missed clinical appointments using transparent,
                interpretable machine learning risk models.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 bg-white py-8">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-4">
          <p>© 2026 CareGap 360 Platform. Production-oriented healthcare engineering.</p>
          <div className="flex space-x-6">
            <span>DPDP Compliance Architecture</span>
            <span>HL7 FHIR Interoperability</span>
            <span>Zero Data Leakage Policy</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

