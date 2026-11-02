"use client";

import { useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { useLanguage } from "./LanguageProvider";

export function DemoBanner() {
  const { t } = useLanguage();
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/v1/health", { credentials: "omit", cache: "no-store", signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((value) => setDemo(value?.demo_mode === true))
      .catch(() => {});
    return () => controller.abort();
  }, []);
  if (!demo) return null;
  return (
    <aside
      aria-label={t("Demo environment")}
      className="flex items-center justify-center gap-3 border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-950"
    >
      <FlaskConical aria-hidden="true" className="h-5 w-5 shrink-0" />
      <p>
        {t("Synthetic demonstration only. Data resets after restarts. Do not upload real medical records.")}
      </p>
    </aside>
  );
}
