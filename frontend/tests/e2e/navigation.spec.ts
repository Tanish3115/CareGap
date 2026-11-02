import { test, expect } from "@playwright/test";
import { openSection } from "./navigation";

test("sidebar separates features, preserves drafts, and supports history and mobile navigation", async ({ page }, testInfo) => {
  const email = `synthetic-navigation-${Date.now()}@example.com`;
  expect((await page.request.post("/api/v1/auth/register", { data: { email, password: "SyntheticNav123!", full_name: "Synthetic Navigation Patient", role: "patient" } })).status()).toBe(201);
  expect((await page.request.post("/api/v1/auth/login", { data: { email, password: "SyntheticNav123!" } })).status()).toBe(200);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Overview", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Medical timeline and follow-ups", exact: true })).toBeHidden();
  await expect(page.getByRole("heading", { name: "Medical Document Vault", exact: true })).toBeHidden();
  await page.screenshot({ path: testInfo.outputPath("overview-desktop.png"), fullPage: true });
  await openSection(page, "consultations");
  await page.getByRole("button", { name: "Add consultation", exact: true }).click();
  await page.getByLabel("Consultation title", { exact: true }).fill("Unsaved synthetic draft");
  await openSection(page, "documents");
  await expect(page.getByLabel("Consultation title", { exact: true })).toBeHidden();
  await page.goBack();
  await expect(page.getByLabel("Consultation title", { exact: true })).toHaveValue("Unsaved synthetic draft");
  await expect(page.getByLabel("Consultation title", { exact: true })).toBeVisible();
  await openSection(page, "documents");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Documents", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Quick actions", exact: true })).toBeHidden();
  for (const id of ["timeline", "medications", "records", "care", "sharing", "profile", "privacy"]) {
    await openSection(page, id);
    await expect(page.locator('nav a[aria-current="page"]')).toHaveAttribute("href", `#${id}`);
    expect(await page.locator("main h1").textContent()).toBeTruthy();
  }
  await openSection(page, "profile");
  await expect(page.getByRole("button", { name: "Save profile", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  const toggle = page.locator('button[aria-controls="workspace-navigation"]');
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  await page.locator('#workspace-navigation a[href="#documents"]').focus();
  await page.keyboard.press("Escape");
  await expect(toggle).toBeFocused();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await openSection(page, "documents");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("documents-mobile.png"), fullPage: true });
  await page.goto("/dashboard#not-a-feature");
  await expect(page.getByRole("heading", { name: "Overview", exact: true })).toBeVisible();
});
