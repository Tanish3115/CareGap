"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Activity, LogOut, ShieldCheck, User as UserIcon } from "lucide-react";
import { clearAuthSession } from "@/lib/auth";

interface NavbarProps {
  user?: {
    full_name: string;
    email: string;
    role: string;
  } | null;
}

export function Navbar({ user }: NavbarProps) {
  const router = useRouter();

  const handleLogout = () => {
    clearAuthSession();
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center space-x-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm">
            <Activity className="h-6 w-6" />
          </div>
          <div>
            <span className="text-xl font-bold tracking-tight text-slate-900">
              CareGap <span className="text-blue-600">360</span>
            </span>
            <span className="hidden text-xs text-slate-500 sm:inline-block sm:ml-2 border-l border-slate-300 pl-2">
              Unified Care Continuity
            </span>
          </div>
        </Link>

        {user ? (
          <div className="flex items-center space-x-4">
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-sm font-semibold text-slate-800">{user.full_name}</span>
              <div className="flex items-center justify-end space-x-1 text-xs text-slate-500">
                <ShieldCheck className="h-3 w-3 text-emerald-600" />
                <span className="capitalize">{user.role}</span>
              </div>
            </div>

            <button
              onClick={handleLogout}
              className="inline-flex items-center space-x-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-sm"
              title="Sign out of CareGap 360"
            >
              <LogOut className="h-3.5 w-3.5 text-slate-500" />
              <span>Logout</span>
            </button>
          </div>
        ) : (
          <div className="flex items-center space-x-3">
            <Link
              href="/login"
              className="text-sm font-medium text-slate-600 hover:text-slate-900 px-3 py-2"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="rounded-md bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
            >
              Get Started
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}

