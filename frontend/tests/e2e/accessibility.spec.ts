import { test, expect, Page } from "@playwright/test";
import { writeFileSync } from "node:fs";
import type { AxeResults, RunOptions } from "axe-core";
import { openSection } from "./navigation";

async function audit(page: Page) {
  await page.addScriptTag({ path: require.resolve("axe-core/axe.min.js") });
  const result = await page.evaluate(async () => {
    const axe = (window as typeof window & { axe: { run: (options: RunOptions) => Promise<AxeResults> } }).axe;
    return axe.run({ runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] } });
  });
  return result.violations.map(violation => ({ id: violation.id, impact: violation.impact,
    nodes: violation.nodes.map(node => ({ target: node.target, failure: node.failureSummary })) }));
}

test("public pages and a patient dashboard pass automated accessibility and keyboard checks", async ({ page }, testInfo) => {
  test.setTimeout(120000);
  const failures = [];
  for (const route of ["/", "/login", "/register"]) {
    await page.goto(route);
    await expect(page).toHaveTitle(/CareGap/);
    await expect(page.locator("main")).toBeVisible();
    await page.keyboard.press("Tab");
    const focused = page.locator(":focus");
    await expect(focused).toBeVisible();
    expect(await focused.evaluate(element => ["A", "BUTTON", "INPUT", "SELECT"].includes(element.tagName))).toBe(true);
    failures.push({ route, violations: await audit(page) });
  }
  const email = `synthetic-a11y-${Date.now()}@example.com`;
  const signup = await page.request.post("/api/v1/auth/register", { data: {
    email, password: "SyntheticA11yBrowser123!", full_name: "Synthetic Accessibility Patient", role: "patient",
  } });
  expect(signup.status()).toBe(201);
  expect((await page.request.post("/api/v1/auth/login", { data: { email, password: "SyntheticA11yBrowser123!" } })).status()).toBe(200);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Synthetic Accessibility Patient", exact: true })).toBeVisible();
  failures.push({ route: "/dashboard", violations: await audit(page) });
  await page.getByRole("button", { name: "Upload Document", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  failures.push({ route: "upload dialog", violations: await audit(page) });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Upload Document", exact: true })).toBeFocused();
  for (const section of ["documents", "timeline", "consultations", "medications", "records", "care", "sharing", "profile", "privacy"]) {
    await openSection(page, section);
    failures.push({ route: `/dashboard#${section}`, violations: await audit(page) });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('button[aria-controls="workspace-navigation"]').click();
  failures.push({ route: "mobile navigation menu", violations: await audit(page) });
  expect(failures.filter(scope => scope.violations.length)).toEqual([]);
  writeFileSync(testInfo.outputPath("accessibility.json"), JSON.stringify({ mode: "automated_synthetic_scope", scopes: failures, independent_audit: false }, null, 2));
  await testInfo.attach("accessibility-scope", { body: "axe-core WCAG A/AA tags on public routes, an empty synthetic patient dashboard and upload dialog; keyboard focus and Escape return. Automated checks do not replace independent assistive-technology review.", contentType: "text/plain" });
});
