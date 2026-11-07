"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  ArrowUpRight,
  ChevronRight,
  ClipboardList,
  FileText,
  HeartPulse,
  History,
  LayoutDashboard,
  Menu,
  Pill,
  Settings2,
  ShieldCheck,
  Stethoscope,
  UserRound,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { useLanguage } from "./LanguageProvider";

type Destination = { id: string; label: string; description: string; icon: LucideIcon };
export const patientDestinations: Destination[] = [
  {
    id: "overview",
    label: "Overview",
    description: "Your health records, clearly organized.",
    icon: LayoutDashboard,
  },
  {
    id: "documents",
    label: "Documents",
    description: "Original documents with upload checksums; clinical contents require review",
    icon: FileText,
  },
  { id: "timeline", label: "Timeline", description: "Unified medical timeline", icon: History },
  {
    id: "consultations",
    label: "Consultations",
    description:
      "Consultations stay linked to their original sources. Corrections retain earlier versions and who recorded them.",
    icon: Stethoscope,
  },
  {
    id: "medications",
    label: "Medications",
    description: "Medication history and reconciliation",
    icon: Pill,
  },
  {
    id: "records",
    label: "Health records",
    description:
      "Track diagnoses, recorded allergies, lab text and care outcomes with sources and history. Patient reports and clinician entries remain distinct. Medication events and staff interventions require clinician write permission.",
    icon: ClipboardList,
  },
  {
    id: "care",
    label: "Care & reminders",
    description: "Care coordination and source overview",
    icon: HeartPulse,
  },
  {
    id: "sharing",
    label: "Sharing & access",
    description:
      "Consent is time-limited. Revocation blocks future requests; it cannot remove copies already downloaded.",
    icon: Users,
  },
  {
    id: "profile",
    label: "My profile",
    description: "Edit your health profile",
    icon: UserRound,
  },
  {
    id: "privacy",
    label: "Privacy & data",
    description: "Privacy and data requests",
    icon: ShieldCheck,
  },
];
export function destinationsFor(userRole: string): Destination[] {
  if (userRole === "admin")
    return [
      {
        id: "verification",
        label: "Professional verification queue",
        description: "Platform operations",
        icon: ShieldCheck,
      },
      {
        id: "operations",
        label: "Organization and user operations",
        description: "Organization, account & privacy operations",
        icon: Settings2,
      },
      { id: "audit", label: "Operational audit events", description: "Record access history", icon: History },
    ];
  if (userRole === "doctor")
    return [
      { id: "patients", label: "Patient access", description: "Request patient access", icon: Users },
      ...patientDestinations.filter((item) =>
        ["documents", "timeline", "consultations", "medications", "records", "care"].includes(item.id),
      ),
    ];
  return patientDestinations;
}

export function WorkspaceSection({
  active,
  id,
  children,
}: {
  active: string;
  id: string;
  children: ReactNode;
}) {
  // Keep forms mounted when navigating so unsaved drafts and review state survive.
  return (
    <div hidden={active !== id} data-workspace-section={id}>
      {children}
    </div>
  );
}

export function WorkspaceNavigation({
  userRole,
  section,
  onSection,
  children,
}: {
  userRole: string;
  section: string;
  onSection: (value: string) => void;
  children: ReactNode;
}) {
  const { t } = useLanguage();
  const destinations = destinationsFor(userRole);
  const current = destinations.find((item) => item.id === section) || destinations[0];
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const sync = () => {
      const id = window.location.hash.slice(1);
      const next =
        destinationsFor(userRole).find((item) => item.id === id)?.id || destinationsFor(userRole)[0].id;
      onSection(next);
      setOpen(false);
    };
    sync();
    const navigate = () => {
      sync();
      requestAnimationFrame(() => heading.current?.focus());
    };
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, [userRole, onSection]);

  return (
    <div className="workspace-shell mx-auto grid w-full max-w-[1600px] lg:grid-cols-[256px_minmax(0,1fr)]">
      <button
        type="button"
        onClick={() => {
          heading.current?.focus();
        }}
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-blue-700 focus:p-3 focus:text-white"
      >
        {t("Skip to content")}
      </button>
      <aside className="workspace-sidebar border-b border-slate-200 bg-white lg:border-b-0 lg:border-r">
        <div className="lg:sticky lg:top-24 lg:max-h-[calc(100dvh-7rem)] lg:overflow-y-auto p-4 lg:p-5">
          <button
            ref={toggle}
            type="button"
            aria-expanded={open}
            aria-controls="workspace-navigation"
            onClick={() => setOpen(!open)}
            className="flex w-full items-center justify-between rounded-xl border border-slate-200 px-4 py-3 font-semibold text-slate-800 lg:hidden"
          >
            <span className="flex items-center gap-3">
              <Menu className="h-5 w-5" aria-hidden="true" />
              {t(current.label)}
            </span>
            {open ? (
              <X className="h-4 w-4" aria-hidden="true" />
            ) : (
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
          <nav
            id="workspace-navigation"
            aria-label={t("Workspace navigation")}
            className={`${open ? "block" : "hidden"} mt-3 lg:mt-0 lg:block`}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setOpen(false);
                toggle.current?.focus();
              }
            }}
          >
            <p className="px-3 pb-3 text-xs font-bold uppercase tracking-widest text-slate-500">
              {t(
                userRole === "patient"
                  ? "My health"
                  : userRole === "doctor"
                    ? "Clinician workspace"
                    : "Platform operations",
              )}
            </p>
            <div className="space-y-1">
              {destinations.map((item) => {
                const Icon = item.icon;
                return (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    aria-current={section === item.id ? "page" : undefined}
                    onClick={() => {
                      setOpen(false);
                      if (section === item.id) heading.current?.focus();
                    }}
                    className={`group flex min-h-12 items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-colors ${section === item.id ? "bg-blue-50 text-blue-800 ring-1 ring-inset ring-blue-100" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}
                  >
                    <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                    <span className="min-w-0 flex-1">{t(item.label)}</span>
                    {section === item.id && <ChevronRight className="h-4 w-4 shrink-0" aria-hidden="true" />}
                  </a>
                );
              })}
            </div>
            <div className="mt-7 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <ShieldCheck className="mb-2 h-5 w-5 text-blue-700" aria-hidden="true" />
              <p className="text-sm font-semibold text-slate-800">{t("Patient-controlled access")}</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-600">
                {t("Original clinical/source text stays unchanged.")}
              </p>
            </div>
          </nav>
        </div>
      </aside>
      <main id="workspace-content" className="min-w-0 px-4 py-6 sm:px-7 lg:p-9">
        <div className="mb-7 border-b border-slate-200 pb-6">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-blue-700">
            {t("CareGap")} <span aria-hidden="true">/</span> {t(userRole)}
          </p>
          <h1
            ref={heading}
            tabIndex={-1}
            className="text-2xl font-bold tracking-tight text-slate-900 outline-none sm:text-3xl"
          >
            {t(current.label)}
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">{t(current.description)}</p>
        </div>
        {children}
      </main>
      {userRole === "patient" && (
        <nav
          aria-label={t("Quick actions")}
          className="patient-mobile-navigation fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-slate-200 bg-white shadow-sm lg:hidden"
        >
          {destinations
            .filter((item) => ["overview", "documents", "consultations", "sharing"].includes(item.id))
            .map((item) => {
              const Icon = item.icon;
              return (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  aria-current={section === item.id ? "page" : undefined}
                  className={`flex min-h-16 flex-col items-center justify-center gap-1 px-1 py-2 text-center text-xs font-medium ${section === item.id ? "bg-blue-50 text-blue-800" : "text-slate-600"}`}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                  <span>{t(item.label)}</span>
                </a>
              );
            })}
        </nav>
      )}
    </div>
  );
}

export function QuickAction({ destination }: { destination: Destination }) {
  const { t } = useLanguage();
  const Icon = destination.icon;
  return (
    <a
      href={`#${destination.id}`}
      className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-blue-300 hover:shadow-md"
    >
      <div className="flex items-center justify-between">
        <span className="rounded-xl bg-blue-50 p-3 text-blue-700">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-blue-700" aria-hidden="true" />
      </div>
      <h3 className="mt-4 text-sm font-semibold text-slate-900">{t(destination.label)}</h3>
      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-600">{t(destination.description)}</p>
    </a>
  );
}
