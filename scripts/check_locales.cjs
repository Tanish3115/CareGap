// Checks static interface copy only. Patient/source values must never be translated.
const fs = require("fs");
const path = require("path");
const ts = require("../frontend/node_modules/typescript");
const root = path.resolve(__dirname, "..");
const catalog = JSON.parse(fs.readFileSync(path.join(root, "frontend/src/locales/hi.json"), "utf8"));
const registry = JSON.parse(fs.readFileSync(path.join(root, "frontend/src/locales/languages.json"), "utf8"));
const unchanged = new Set(["A+", "A-", "AB+", "AB-", "B+", "B-", "O+", "O-", "CareGap", "KB", "SHA-256:", "SHA-256: {value0}", "patient@example.com", "user@example.com", "• {value0}"]);
const issues = [];
const placeholders = value => [...value.matchAll(/\{([A-Za-z0-9_]+)\}/g)].map(match => match[1]).sort().join(",");
const requiredLocales = ["en", "hi", "kn", "te", "ta", "ml"];
if (Object.keys(registry).sort().join(",") !== requiredLocales.sort().join(",")) issues.push("The registry must contain exactly English, Hindi, Kannada, Telugu, Tamil and Malayalam.");
const coverage = {};
const nativeExceptions = new Set([...unchanged, "sms", "whatsapp"]);
const nativeScripts = { hi: /\p{Script=Devanagari}/u, kn: /\p{Script=Kannada}/u, te: /\p{Script=Telugu}/u, ta: /\p{Script=Tamil}/u, ml: /\p{Script=Malayalam}/u };
for (const [locale, language] of Object.entries(registry)) {
  if (locale === "en") { coverage.en = "English source copy"; continue; }
  if (!language.catalog || !/^[a-z]{2}\.json$/.test(language.catalog)) { issues.push("Invalid catalog: " + locale); continue; }
  const entries = JSON.parse(fs.readFileSync(path.join(root, "frontend/src/locales", language.catalog), "utf8"));
  for (const key of Object.keys(catalog)) if (!entries[key]) issues.push(`Missing ${locale} translation: ${key}`);
  for (const [key, value] of Object.entries(entries)) {
    if (typeof value !== "string" || !value.trim() || placeholders(key) !== placeholders(value)) issues.push(`Invalid ${locale} translation/placeholders: ${key}`);
    if (!Object.prototype.hasOwnProperty.call(catalog, key)) issues.push(`Unknown ${locale} translation key: ${key}`);
    if (key === value && !unchanged.has(key)) issues.push(`Untranslated ${locale} interface text: ${key}`);
    if (typeof value === "string" && !nativeExceptions.has(key) && !nativeScripts[locale].test(value)) issues.push(`Missing native script or damaged ${locale} text: ${key}`);
    if (typeof value === "string" && (value.includes("\uFFFD") || /\?{2,}/.test(value))) issues.push(`Damaged ${locale} text: ${key}`);
  }
  coverage[locale] = { entries: Object.keys(entries).length, coveredReferenceKeys: Object.keys(catalog).filter(key => entries[key]).length, referenceKeys: Object.keys(catalog).length };
}
for (const [key, value] of Object.entries(catalog)) {
  if (!value.trim() || placeholders(key) !== placeholders(value)) issues.push("Invalid translation/placeholders: " + key);
  if (key === value && !unchanged.has(key)) issues.push("Untranslated interface text: " + key);
}
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(file);
    else if (file.endsWith(".tsx") && !file.endsWith("LanguageProvider.tsx")) {
      const source = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
      function visit(node) {
        if (ts.isJsxText(node) && /[A-Za-z]/.test(node.getText(source))) issues.push("Static text bypasses language catalog: " + path.relative(root, file));
        if (ts.isJsxAttribute(node) && ["title", "description", "placeholder", "aria-label", "alt"].includes(node.name.getText(source)) && node.initializer && ts.isStringLiteral(node.initializer) && /[A-Za-z]/.test(node.initializer.text) && !unchanged.has(node.initializer.text)) issues.push("Static attribute bypasses language catalog: " + path.relative(root, file) + ": " + node.initializer.text);
        if (ts.isJsxExpression(node) && (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent)) && node.expression && (ts.isStringLiteral(node.expression) || ts.isNoSubstitutionTemplateLiteral(node.expression)) && /[A-Za-z]/.test(node.expression.text)) issues.push("Static expression bypasses language catalog: " + path.relative(root, file));
        if (ts.isCallExpression(node) && node.expression.getText(source) === "t" && node.arguments[0] && ts.isStringLiteral(node.arguments[0]) && !catalog[node.arguments[0].text]) issues.push("Missing Hindi copy: " + node.arguments[0].text);
        ts.forEachChild(node, visit);
      }
      visit(source);
    }
  }
}
walk(path.join(root, "frontend/src"));
// Exercise the actual translator, including untrusted server-error fallback text.
const assert = require("node:assert/strict");
const translatorSource = fs.readFileSync(path.join(root, "frontend/src/lib/i18n.ts"), "utf8");
const translatorCode = ts.transpileModule(translatorSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText;
const translatorExports = {};
new Function("require", "exports", translatorCode)(name => {
  if (!/^@\/locales\/[a-z]+\.json$/.test(name)) throw new Error("Unexpected translator dependency");
  return JSON.parse(fs.readFileSync(path.join(root, "frontend/src", name.slice(2)), "utf8"));
}, translatorExports);
for (const locale of requiredLocales) {
  for (const unknown of ["constructor", "toString", "__proto__", "hasOwnProperty"]) assert.equal(translatorExports.translate(unknown, locale), unknown);
  assert.equal(translatorExports.translate("Unknown {value0}", locale, { value0: "SYNTHETIC-A" }), "Unknown SYNTHETIC-A");
  assert.equal(translatorExports.isLocale(locale), true);
  assert.equal(translatorExports.hasEnglishFallback(locale), false);
}
for (const unsupported of ["bn", "constructor", null, {}, "EN"]) assert.equal(translatorExports.isLocale(unsupported), false);
if (issues.length) { process.stderr.write(issues.join("\n") + "\n"); process.exitCode = 1; }
else process.stdout.write("Locale checks passed: " + JSON.stringify(coverage) + "\n");
