import languageRegistry from "@/locales/languages.json";
import hindi from "@/locales/hi.json";
import tamil from "@/locales/ta.json";
import telugu from "@/locales/te.json";
import kannada from "@/locales/kn.json";
import malayalam from "@/locales/ml.json";

export type Locale = keyof typeof languageRegistry;
export type TranslationValues = Record<string, string | number>;
export const languages = languageRegistry;
const catalogs: Record<Locale, Record<string, string>> = {
  en: {},
  hi: hindi,
  ta: tamil,
  te: telugu,
  kn: kannada,
  ml: malayalam,
};
const foldedCatalogs = Object.fromEntries(
  Object.entries(catalogs).map(([locale, entries]) => [
    locale,
    Object.fromEntries(Object.entries(entries).map(([key, value]) => [key.toLowerCase(), value])),
  ]),
) as typeof catalogs;

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && Object.hasOwn(languages, value);
}

export function translate(text: string, locale: Locale, values: TranslationValues = {}) {
  // Only interface copy is passed here. Clinical/source text is rendered separately.
  const own = (entries: Record<string, string>, key: string) =>
    Object.hasOwn(entries, key) && typeof entries[key] === "string" ? entries[key] : undefined;
  const template = own(catalogs[locale], text) ?? own(foldedCatalogs[locale], text.toLowerCase()) ?? text;
  return template.replace(/\{([A-Za-z0-9_]+)\}/g, (match, key) =>
    Object.hasOwn(values, key) ? String(values[key]) : match,
  );
}

export function hasEnglishFallback(locale: Locale) {
  return locale !== "en" && Object.keys(hindi).some((key) => !catalogs[locale][key]);
}
