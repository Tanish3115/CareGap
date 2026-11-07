"use client";

import { useLanguage } from "@/components/LanguageProvider";

import type React from "react";
import { useId, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, Lock, Mail, User, AlertCircle, Loader2, Stethoscope, UserCheck } from "lucide-react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { setAuthSession } from "@/lib/auth";

export default function RegisterPage() {
  const { t } = useLanguage();
  const formId = useId();
  const router = useRouter();
  const [role, setRole] = useState<"patient" | "doctor">("patient");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");

  // Doctor-specific
  const [licenseNumber, setLicenseNumber] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [hospitalAffiliation, setHospitalAffiliation] = useState("");

  // Patient-specific
  const [bloodGroup, setBloodGroup] = useState("");
  const [emergencyContact, setEmergencyContact] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);

      const payload: Record<string, unknown> = {
        email,
        password,
        full_name: fullName,
        role,
        phone: phone || undefined,
      };

      if (role === "doctor") {
        if (!licenseNumber || !specialization) {
          setError("License number and specialization are required for doctors.");
          setLoading(false);
          return;
        }
        payload.license_number = licenseNumber;
        payload.specialization = specialization;
        payload.hospital_affiliation = hospitalAffiliation || undefined;
      } else {
        payload.blood_group = bloodGroup || undefined;
        payload.emergency_contact = emergencyContact || undefined;
      }

      await api.auth.register(payload);

      // Auto login after registration
      const authData = await api.auth.login({ email, password });
      setAuthSession(authData);
      router.push("/dashboard");
    } catch (err) {
      setError(errorMessage(err, "Registration failed. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen flex flex-col justify-center bg-slate-50 py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <Link href="/" aria-label={t("CareGap")} className="flex items-center justify-center space-x-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white shadow-md">
            <Activity className="h-7 w-7" />
          </div>
        </Link>
        <h2 className="mt-4 text-center text-2xl font-extrabold tracking-tight text-slate-900">
          {" "}
          {t("Create Your CareGap 360 Account")}{" "}
        </h2>
        <p className="mt-1 text-center text-xs text-slate-500">
          {" "}
          {t("Doctors require professional verification before requesting patient access")}{" "}
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-lg">
        <div className="rounded-2xl border border-slate-200 bg-white px-6 py-8 shadow-sm sm:px-10">
          {/* Role Selector Tabs */}
          <div className="grid grid-cols-2 gap-3 mb-6 p-1 bg-slate-100 rounded-xl">
            <button
              type="button"
              onClick={() => setRole("patient")}
              className={`flex items-center justify-center space-x-2 py-2 text-xs font-semibold rounded-lg transition-all ${
                role === "patient"
                  ? "bg-white text-blue-700 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <UserCheck className="h-4 w-4" />
              <span>{t("Patient Account")}</span>
            </button>
            <button
              type="button"
              onClick={() => setRole("doctor")}
              className={`flex items-center justify-center space-x-2 py-2 text-xs font-semibold rounded-lg transition-all ${
                role === "doctor" ? "bg-white text-blue-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Stethoscope className="h-4 w-4" />
              <span>{t("Doctor / Clinician")}</span>
            </button>
          </div>

          {error && (
            <div className="mb-6 flex items-center space-x-2 rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />
              <span>{t(error)}</span>
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label
                htmlFor={`${formId}-field-1`}
                className="block text-xs font-semibold text-slate-700 mb-1"
              >
                {" "}
                {t("Full Legal Name")}{" "}
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <User className="h-4 w-4" />
                </div>
                <input
                  id={`${formId}-field-1`}
                  type="text"
                  aria-label={t("Full Legal Name")}
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder={t("e.g. Dr. Jane Doe or Alice Johnson")}
                  className="w-full rounded-lg border border-slate-300 pl-10 pr-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor={`${formId}-field-2`}
                  className="block text-xs font-semibold text-slate-700 mb-1"
                >
                  {" "}
                  {t("Email Address")}{" "}
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                    <Mail className="h-4 w-4" />
                  </div>
                  <input
                    id={`${formId}-field-2`}
                    type="email"
                    aria-label={t("Email Address")}
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={t("user@example.com")}
                    className="w-full rounded-lg border border-slate-300 pl-10 pr-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                  />
                </div>
              </div>

              <div>
                <label
                  htmlFor={`${formId}-field-3`}
                  className="block text-xs font-semibold text-slate-700 mb-1"
                >
                  {" "}
                  {t("Phone (Optional)")}{" "}
                </label>
                <input
                  id={`${formId}-field-3`}
                  type="tel"
                  aria-label={t("Phone")}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+1 (555) 000-0000"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor={`${formId}-field-4`}
                className="block text-xs font-semibold text-slate-700 mb-1"
              >
                {" "}
                {t("Password (min 12 characters)")}{" "}
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id={`${formId}-field-4`}
                  type="password"
                  aria-label={t("Password")}
                  required
                  minLength={12}
                  maxLength={72}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-slate-300 pl-10 pr-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                />
              </div>
            </div>

            {/* Doctor specific fields */}
            {role === "doctor" && (
              <div className="space-y-3 rounded-xl bg-slate-50 p-4 border border-slate-200">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  {" "}
                  {t("Clinician Verification Details")}{" "}
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label
                      htmlFor={`${formId}-field-5`}
                      className="block text-xs font-semibold text-slate-600 mb-1"
                    >
                      {" "}
                      {t("Medical License Number *")}{" "}
                    </label>
                    <input
                      id={`${formId}-field-5`}
                      type="text"
                      aria-label={t("Medical License Number")}
                      required
                      value={licenseNumber}
                      onChange={(e) => setLicenseNumber(e.target.value)}
                      placeholder={t("e.g. MED-847291")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 outline-none bg-white"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor={`${formId}-field-6`}
                      className="block text-xs font-semibold text-slate-600 mb-1"
                    >
                      {" "}
                      {t("Specialization *")}{" "}
                    </label>
                    <input
                      id={`${formId}-field-6`}
                      type="text"
                      aria-label={t("Specialization")}
                      required
                      value={specialization}
                      onChange={(e) => setSpecialization(e.target.value)}
                      placeholder={t("e.g. Cardiology, Internal Med")}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 outline-none bg-white"
                    />
                  </div>
                </div>
                <div>
                  <label
                    htmlFor={`${formId}-field-7`}
                    className="block text-xs font-semibold text-slate-600 mb-1"
                  >
                    {" "}
                    {t("Primary Hospital / Clinic Affiliation")}{" "}
                  </label>
                  <input
                    id={`${formId}-field-7`}
                    type="text"
                    aria-label={t("Hospital or Clinic Affiliation")}
                    value={hospitalAffiliation}
                    onChange={(e) => setHospitalAffiliation(e.target.value)}
                    placeholder={t("e.g. Metropolitan General Hospital")}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 outline-none bg-white"
                  />
                </div>
              </div>
            )}

            {/* Patient specific fields */}
            {role === "patient" && (
              <div className="space-y-3 rounded-xl bg-slate-50 p-4 border border-slate-200">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  {" "}
                  {t("Patient Health Profile")}{" "}
                </span>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label
                      htmlFor={`${formId}-field-8`}
                      className="block text-xs font-semibold text-slate-600 mb-1"
                    >
                      {" "}
                      {t("Blood Group (Optional)")}{" "}
                    </label>
                    <select
                      id={`${formId}-field-8`}
                      aria-label={t("Blood Group")}
                      value={bloodGroup}
                      onChange={(e) => setBloodGroup(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 outline-none bg-white"
                    >
                      <option value="">{t("Select...")}</option>
                      <option value="A+">{t("A+")}</option>
                      <option value="A-">{t("A-")}</option>
                      <option value="B+">{t("B+")}</option>
                      <option value="B-">{t("B-")}</option>
                      <option value="AB+">{t("AB+")}</option>
                      <option value="AB-">{t("AB-")}</option>
                      <option value="O+">{t("O+")}</option>
                      <option value="O-">{t("O-")}</option>
                    </select>
                  </div>
                  <div>
                    <label
                      htmlFor={`${formId}-field-9`}
                      className="block text-xs font-semibold text-slate-600 mb-1"
                    >
                      {" "}
                      {t("Emergency Contact")}{" "}
                    </label>
                    <input
                      id={`${formId}-field-9`}
                      type="tel"
                      aria-label={t("Emergency Contact")}
                      value={emergencyContact}
                      onChange={(e) => setEmergencyContact(e.target.value)}
                      placeholder="+1 (555) 999-8888"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 outline-none bg-white"
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="w-full inline-flex items-center justify-center space-x-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                <span>{loading ? t("Creating Account...") : t("Create Account")}</span>
              </button>
            </div>
          </form>

          <div className="mt-6 border-t border-slate-100 pt-5 text-center text-xs text-slate-600">
            {" "}
            {t("Already have an account?")}{" "}
            <Link href="/login" className="font-semibold text-blue-600 hover:text-blue-700">
              {" "}
              {t("Sign In")}{" "}
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
