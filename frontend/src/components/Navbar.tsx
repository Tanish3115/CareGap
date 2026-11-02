"use client";

import { useLanguage } from "@/components/LanguageProvider";

import { LanguageSwitcher } from "./LanguageProvider";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, LogOut, ShieldCheck } from "lucide-react";
import { clearAuthSession } from "@/lib/auth";
import { api } from "@/lib/api";

interface NavbarProps {
  user?: {
    full_name: string;
    email: string;
    role: string;
  } | null;
}

export function Navbar({ user }: NavbarProps) {
  const { t } = useLanguage();
  const router = useRouter();

  const handleLogout = async () => {
    try {
      await api.auth.logout();
      clearAuthSession();
      router.push("/login");
    } catch {
      window.alert(t("Sign out failed. Please try again."));
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex min-h-20 max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <Link href={user ? "/dashboard" : "/"} className="flex shrink-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm">
            <Activity className="h-6 w-6" />
          </div>
          <div>
            <span className="whitespace-nowrap text-xl font-bold tracking-tight text-slate-900">
              {" "}
              {t("CareGap")} <span className="text-blue-600">360</span>
            </span>
            <span className="hidden text-xs text-slate-500 xl:inline-block xl:ml-2 border-l border-slate-300 pl-2">
              {" "}
              {t("Unified Care Continuity")}{" "}
            </span>
          </div>
        </Link>

        <LanguageSwitcher />
        {user ? (
          <div className="ml-auto flex min-w-0 flex-wrap items-center gap-3">
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-sm font-semibold text-slate-800">{user.full_name}</span>
              <div className="flex items-center justify-end space-x-1 text-xs text-slate-500">
                <ShieldCheck className="h-3 w-3 text-emerald-600" />
                <span className="capitalize">{t(user.role)}</span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex items-center space-x-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-sm"
              title={t("Sign out of CareGap 360")}
            >
              <LogOut className="h-3.5 w-3.5 text-slate-500" />
              <span>{t("Logout")}</span>
            </button>
          </div>
        ) : (
          <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-2">
            <Link href="/login" className="text-sm font-medium text-slate-600 hover:text-slate-900 px-3 py-2">
              {" "}
              {t("Sign In")}{" "}
            </Link>
            <Link
              href="/register"
              className="rounded-md bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
            >
              {" "}
              {t("Get Started")}{" "}
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
