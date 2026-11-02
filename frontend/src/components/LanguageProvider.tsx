"use client";

import { createContext, useCallback, useContext, useEffect, useId, useState } from "react";
import {
  hasEnglishFallback,
  isLocale,
  languages,
  type Locale,
  translate,
  type TranslationValues,
} from "@/lib/i18n";

const LanguageContext = createContext({
  locale: "en" as Locale,
  setLocale: (locale: Locale) => {
    void locale;
  },
  t: (text: string, values?: TranslationValues) => translate(text, "en", values),
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  // Start identically on server/client; read only the language preference after hydration.
  const [locale, setLocaleState] = useState<Locale>("en");
  useEffect(() => {
    try {
      const saved = localStorage.getItem("caregap-language");
      if (isLocale(saved)) setLocaleState(saved);
    } catch {}
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = languages[locale].direction;
  }, [locale]);
  const setLocale = useCallback((next: Locale) => {
    if (!isLocale(next)) return;
    setLocaleState(next);
    try {
      localStorage.setItem("caregap-language", next);
    } catch {}
  }, []);
  const t = useCallback(
    (text: string, values?: TranslationValues) => translate(text, locale, values),
    [locale],
  );
  return <LanguageContext.Provider value={{ locale, setLocale, t }}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  return useContext(LanguageContext);
}

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useLanguage();
  const id = useId();
  return (
    <div className="min-w-0 text-xs">
      <label className="sr-only" htmlFor={id}>
        Application language / भाषा
      </label>
      <select
        id={id}
        aria-describedby={hasEnglishFallback(locale) ? `${id}-fallback` : undefined}
        className="max-w-28 rounded border border-slate-300 bg-white px-1 py-2 text-slate-800"
        value={locale}
        onChange={(event) => {
          if (isLocale(event.target.value)) setLocale(event.target.value);
        }}
      >
        {Object.entries(languages).map(([code, language]) => (
          <option key={code} value={code} lang={code}>
            {language.nativeName}
          </option>
        ))}
      </select>
      {hasEnglishFallback(locale) && (
        <span
          id={`${id}-fallback`}
          title={t("Some interface text uses English fallback.")}
          className="block max-w-28 text-[10px] leading-tight text-slate-600"
        >
          {t("English fallback")}
        </span>
      )}
    </div>
  );
}
