"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { Activity, Loader2, Mail, ShieldCheck } from "lucide-react";
import { LanguageSwitcher, useLanguage } from "./LanguageProvider";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";

const invalidLink = "This password reset link is invalid or has expired. Please request a new link.";
const field =
  "mt-2 min-h-12 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base text-slate-900";
const button =
  "inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-3 text-base font-semibold text-white hover:bg-blue-700 disabled:opacity-50";

export function PasswordRecovery({ mode }: { mode: "request" | "reset" }) {
  const { t } = useLanguage();
  const formId = useId();
  const readLink = useRef(false);
  const [token, setToken] = useState<string | null>(mode === "reset" ? null : "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [complete, setComplete] = useState(false);
  const [delivery, setDelivery] = useState<"local" | "email">("email");
  const [error, setError] = useState("");
  useEffect(() => {
    if (mode !== "reset" || readLink.current) return;
    readLink.current = true;
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
    setToken(/^[A-Za-z0-9_-]{43}$/.test(value) ? value : "");
    // The secret stays in memory, never in a server URL, storage or a rendered field.
    window.history.replaceState(window.history.state, "", window.location.pathname);
  }, [mode]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (mode === "reset") {
      if (password !== confirmation) {
        setError("Passwords do not match.");
        return;
      }
      if (password.length < 12 || password.length > 72 || new TextEncoder().encode(password).length > 72) {
        setError("Password must contain 12–72 characters and at most 72 UTF-8 bytes.");
        return;
      }
    }
    setBusy(true);
    try {
      if (mode === "request") {
        const result = await api.auth.forgotPassword(email.trim());
        setDelivery(result.delivery);
      } else await api.auth.resetPassword(token || "", password);
      setComplete(true);
      setToken("");
      setPassword("");
      setConfirmation("");
    } catch (failure) {
      const message = errorMessage(failure, "Request failed. Please try again.");
      if (mode === "reset" && message === invalidLink) setToken("");
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  const missingToken = mode === "reset" && token === "" && !complete;
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-between gap-4">
          <Link
            href="/"
            aria-label={t("CareGap")}
            className="inline-flex items-center gap-2 font-bold text-slate-900"
          >
            <span className="rounded-xl bg-blue-600 p-2 text-white">
              <Activity className="h-6 w-6" aria-hidden="true" />
            </span>
            {t("CareGap")}
          </Link>
          <LanguageSwitcher />
        </div>
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <h1 className="text-2xl font-bold text-slate-900">
            {complete
              ? mode === "request"
                ? delivery === "local"
                  ? t("Password reset requested")
                  : t("Check your email")
                : t("Password reset complete")
              : missingToken
                ? t("Reset link unavailable")
                : mode === "request"
                  ? t("Forgot your password?")
                  : t("Choose a new password")}
          </h1>
          {complete ? (
            <div role="status" className="mt-5 space-y-4">
              <ShieldCheck className="h-8 w-8 text-emerald-700" aria-hidden="true" />
              <p className="text-base leading-relaxed text-slate-700">
                {mode === "request"
                  ? delivery === "local"
                    ? t(
                        "This local app saves reset emails on this computer. It does not send them to your inbox.",
                      )
                    : t("If an active account exists for this email, a password reset link will be sent.")
                  : t("Your password has been reset. Sign in with your new password.")}
              </p>
              {mode === "request" ? (
                <>
                  <p className="text-sm leading-relaxed text-slate-600">
                    {delivery === "local"
                      ? t(
                          "Ask the app operator for your reset link. Real email delivery requires a configured email provider.",
                        )
                      : t("Check your inbox and spam folder. Wait a minute before requesting another link.")}
                  </p>
                  <button
                    type="button"
                    className="min-h-11 rounded-lg border px-4 py-2 text-sm font-semibold text-blue-700"
                    onClick={() => setComplete(false)}
                  >
                    {t("Send another link")}
                  </button>
                </>
              ) : (
                <Link href="/login" className={button}>
                  {t("Sign In")}
                </Link>
              )}
            </div>
          ) : mode === "reset" && token === null ? (
            <p role="status" className="mt-5 flex items-center gap-2 text-slate-600">
              <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
              {t("Checking reset link…")}
            </p>
          ) : missingToken ? (
            <div className="mt-5 space-y-5">
              <p role="alert" className="text-base leading-relaxed text-slate-700">
                {t(invalidLink)}
              </p>
              <Link href="/forgot-password" className={button}>
                {t("Request a new reset link")}
              </Link>
            </div>
          ) : (
            <>
              <p className="mt-3 text-base leading-relaxed text-slate-600">
                {mode === "request"
                  ? t("Enter your account email to request a password reset.")
                  : t("Choose a new password. Existing sessions will be signed out.")}
              </p>
              {error && (
                <p
                  role="alert"
                  className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
                >
                  {t(error)}
                </p>
              )}
              <form onSubmit={submit} className="mt-6 space-y-5">
                {mode === "request" ? (
                  <div>
                    <label htmlFor={`${formId}-email`} className="text-sm font-semibold text-slate-700">
                      {t("Email Address")}
                    </label>
                    <input
                      id={`${formId}-email`}
                      type="email"
                      autoComplete="email"
                      required
                      maxLength={255}
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      className={field}
                      disabled={busy}
                    />
                  </div>
                ) : (
                  <>
                    <div>
                      <label htmlFor={`${formId}-password`} className="text-sm font-semibold text-slate-700">
                        {t("New password")}
                      </label>
                      <input
                        id={`${formId}-password`}
                        type="password"
                        autoComplete="new-password"
                        required
                        minLength={12}
                        maxLength={72}
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        aria-describedby={`${formId}-hint`}
                        className={field}
                        disabled={busy}
                      />
                      <p id={`${formId}-hint`} className="mt-2 text-sm text-slate-600">
                        {t("Password must contain 12–72 characters and at most 72 UTF-8 bytes.")}
                      </p>
                    </div>
                    <div>
                      <label htmlFor={`${formId}-confirm`} className="text-sm font-semibold text-slate-700">
                        {t("Confirm new password")}
                      </label>
                      <input
                        id={`${formId}-confirm`}
                        type="password"
                        autoComplete="new-password"
                        required
                        minLength={12}
                        maxLength={72}
                        value={confirmation}
                        onChange={(event) => setConfirmation(event.target.value)}
                        className={field}
                        disabled={busy}
                      />
                    </div>
                  </>
                )}
                <button type="submit" disabled={busy} className={button}>
                  {busy ? (
                    <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                  ) : mode === "request" ? (
                    <Mail className="h-5 w-5" aria-hidden="true" />
                  ) : null}
                  {mode === "request"
                    ? busy
                      ? t("Sending reset link…")
                      : t("Send reset link")
                    : busy
                      ? t("Resetting password…")
                      : t("Reset password")}
                </button>
              </form>
            </>
          )}
          <div className="mt-6 border-t border-slate-100 pt-4">
            <Link
              href="/login"
              className="inline-flex min-h-11 items-center rounded px-1 text-sm font-semibold text-blue-700 hover:text-blue-800"
            >
              {t("Back to sign in")}
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
