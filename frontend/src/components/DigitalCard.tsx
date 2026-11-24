"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Copy,
  CreditCard,
  Download,
  FileText,
  Loader2,
  Pencil,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import { useLanguage } from "./LanguageProvider";
import { api } from "@/lib/api";
import { createCardImage, saveCardImage, type CardImage } from "@/lib/digital-card-download";
import type { DoctorProfile, PatientCard, PatientProfile, User } from "@/types";

function CardField({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={`min-w-0 ${wide ? "col-span-2" : ""}`}>
      <dt title={label} className="truncate text-xs leading-4 text-slate-600">
        {label}
      </dt>
      <dd title={value} className="truncate text-sm font-semibold leading-5 text-slate-900">
        {value}
      </dd>
    </div>
  );
}

function DownloadCard({
  identity,
  filename,
  prepare,
}: {
  identity: string;
  filename: string;
  prepare: (signal: AbortSignal) => Promise<CardImage>;
}) {
  const { t } = useLanguage();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), [identity]);
  return (
    <>
      <button
        type="button"
        className="inline-flex items-center gap-2 rounded-lg border border-emerald-300 px-3 py-2 text-sm font-semibold text-emerald-900 hover:bg-emerald-50 disabled:opacity-60"
        disabled={busy}
        onClick={async () => {
          const controller = new AbortController();
          pending.current?.abort();
          pending.current = controller;
          setBusy(true);
          setError(false);
          try {
            const data = await prepare(controller.signal);
            if (controller.signal.aborted) return;
            const image = await createCardImage(data);
            if (!controller.signal.aborted) saveCardImage(image, filename);
          } catch {
            if (!controller.signal.aborted) setError(true);
          } finally {
            if (!controller.signal.aborted) setBusy(false);
          }
        }}
      >
        {busy ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <Download className="h-4 w-4" aria-hidden="true" />
        )}
        {busy ? t("Preparing card…") : t("Download card")}
      </button>
      {error && (
        <p role="alert" className="w-full text-sm text-red-700">
          {t("Card unavailable. Refresh your account and try again.")}
        </p>
      )}
    </>
  );
}

function CardFace({ children }: { children: ReactNode }) {
  return (
    <div data-digital-card-face className="digital-card-face">
      {children}
    </div>
  );
}

export function PatientDigitalCard({
  patient,
  ownAccount = false,
}: {
  patient: PatientCard & Partial<PatientProfile>;
  ownAccount?: boolean;
}) {
  const { t, locale } = useLanguage();
  const [copyStatus, setCopyStatus] = useState("");
  const dateOfBirth = (value?: string) =>
    value
      ? new Date(`${value}T00:00:00`).toLocaleDateString(locale, {
          year: "numeric",
          month: "short",
          day: "numeric",
        })
      : t("Not recorded");
  const fields = (profile: Partial<PatientProfile>) => [
    { label: t("Date of birth"), value: dateOfBirth(profile.date_of_birth) },
    { label: t("Blood group"), value: profile.blood_group || t("Not recorded") },
    { label: t("Phone number"), value: profile.phone || t("Not recorded") },
    { label: t("Emergency contact"), value: profile.emergency_contact || t("Not recorded") },
  ];
  return (
    <section aria-label={t("Patient digital card")} className="digital-card">
      <CardFace>
        <div className="flex min-w-0 items-center justify-between gap-2">
          <span className="inline-flex shrink-0 items-center gap-1.5 text-sm font-bold text-emerald-900">
            <CreditCard className="h-4 w-4" aria-hidden="true" />
            {t("CareGap")} 360
          </span>
          <span title={t("Patient digital card")} className="truncate text-xs text-emerald-900">
            {t("Patient account")}
          </span>
        </div>
        <div className="mt-2 flex min-w-0 items-start justify-between gap-3">
          <h2
            title={patient.full_name}
            className="line-clamp-2 min-w-0 text-base font-bold leading-5 text-slate-900"
          >
            {patient.full_name}
          </h2>
          <dl className="shrink-0 text-right">
            <dt className="text-xs leading-4 text-emerald-900">{t("Patient ID")}</dt>
            <dd className="select-all font-mono text-2xl font-bold leading-7 tracking-wider text-emerald-950">
              {patient.patient_code}
            </dd>
          </dl>
        </div>
        {ownAccount ? (
          <dl className="mt-2 grid min-w-0 grid-cols-2 gap-x-3 gap-y-1.5">
            {fields(patient).map((field) => (
              <CardField key={field.label} {...field} />
            ))}
          </dl>
        ) : (
          <p className="mt-auto pt-2 text-xs leading-4 text-slate-600">
            {t("Only patient identity is shown. Records follow the approved sharing scope.")}
          </p>
        )}
      </CardFace>
      <div className="mt-2 flex flex-wrap items-center justify-end gap-1.5">
        <button
          type="button"
          aria-label={t("Copy patient ID")}
          title={t("Copy patient ID")}
          className="inline-flex w-11 items-center justify-center rounded-lg border border-slate-200 text-emerald-900 hover:bg-emerald-50"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(patient.patient_code);
              setCopyStatus("Patient ID copied.");
            } catch {
              setCopyStatus("Unable to copy. Select and copy your patient ID.");
            }
          }}
        >
          <Copy className="h-4 w-4" aria-hidden="true" />
        </button>
        <DownloadCard
          identity={patient.id}
          filename={`caregap-patient-${patient.patient_code}.png`}
          prepare={async (signal) => {
            const fresh = ownAccount
              ? await api.patients.getProfile({ signal })
              : await api.patients.getCard(patient.id, { signal });
            if (fresh.id !== patient.id) throw new Error("Card context changed");
            return {
              kind: "patient",
              locale,
              title: t("Patient digital card"),
              name: fresh.full_name,
              identifier: { label: t("Patient ID"), value: fresh.patient_code },
              fields: ownAccount ? fields(fresh) : [],
              footer: ownAccount
                ? undefined
                : t("Only patient identity is shown. Records follow the approved sharing scope."),
            };
          }}
        />
        <a
          href={ownAccount ? "#profile" : "#documents"}
          aria-label={ownAccount ? t("Edit your health profile") : t("View shared records")}
          title={ownAccount ? t("Edit your health profile") : t("View shared records")}
          className="inline-flex min-h-11 w-11 items-center justify-center rounded-lg border border-slate-200 text-emerald-900 hover:bg-emerald-50"
        >
          {ownAccount ? (
            <Pencil className="h-4 w-4" aria-hidden="true" />
          ) : (
            <FileText className="h-4 w-4" aria-hidden="true" />
          )}
        </a>
        {copyStatus && (
          <p role="status" className="w-full text-right text-sm text-slate-700">
            {t(copyStatus)}
          </p>
        )}
      </div>
    </section>
  );
}

export function DoctorDigitalCard({ user }: { user: User & { doctor: DoctorProfile } }) {
  const { t, locale } = useLanguage();
  const doctor = user.doctor;
  const verified = doctor.verification_status === "verified";
  const fields = (profile: DoctorProfile) => [
    { label: t("Medical License Number"), value: profile.license_number },
    { label: t("Specialization"), value: profile.specialization },
    { label: t("Hospital / Clinic Affiliation"), value: profile.hospital_affiliation || t("Not recorded") },
  ];
  return (
    <section aria-label={t("Doctor digital card")} className="digital-card">
      <CardFace>
        <div className="flex min-w-0 items-center justify-between gap-2">
          <span className="inline-flex shrink-0 items-center gap-1.5 text-sm font-bold text-emerald-900">
            <Stethoscope className="h-4 w-4" aria-hidden="true" />
            {t("CareGap")} 360
          </span>
          <span
            title={`${t("Verification status:")} ${t(doctor.verification_status)}`}
            className={`inline-flex min-w-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs ${verified ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-900"}`}
          >
            {verified && <ShieldCheck className="h-3 w-3 shrink-0" aria-hidden="true" />}
            <span className="sr-only">{t("Verification status:")} </span>
            <span className="truncate">{t(doctor.verification_status)}</span>
          </span>
        </div>
        <h2 title={user.full_name} className="mt-2 line-clamp-2 text-base font-bold leading-5 text-slate-900">
          {user.full_name}
        </h2>
        <dl className="mt-2 grid min-w-0 grid-cols-2 gap-x-3 gap-y-1.5">
          {fields(doctor).map((field, index) => (
            <CardField key={field.label} {...field} wide={index === 0} />
          ))}
        </dl>
      </CardFace>
      <div className="mt-2 flex flex-wrap justify-end gap-2">
        <DownloadCard
          identity={doctor.id}
          filename="caregap-doctor-card.png"
          prepare={async (signal) => {
            const fresh = await api.auth.me({ signal });
            if (fresh.id !== user.id || fresh.role !== "doctor" || fresh.doctor?.id !== doctor.id)
              throw new Error("Card context changed");
            return {
              kind: "doctor",
              locale,
              title: `${t("Doctor digital card")} · ${t(fresh.doctor.verification_status)}`,
              name: fresh.full_name,
              fields: fields(fresh.doctor),
            };
          }}
        />
      </div>
    </section>
  );
}
