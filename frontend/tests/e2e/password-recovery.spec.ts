import { test, expect, type Page } from "@playwright/test";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import type { AxeResults, RunOptions } from "axe-core";

const mailbox = path.resolve(".tools/e2e-reset-mail");
const originalPassword = "SyntheticOriginal123!";
const newPassword = "SyntheticRecovered123!";

async function checkAccessibility(page: Page) {
  await page.addScriptTag({ path: require.resolve("axe-core/axe.min.js") });
  const violations = await page.evaluate(async () => {
    const axe = (window as typeof window & { axe: { run: (options: RunOptions) => Promise<AxeResults> } }).axe;
    return (await axe.run({ runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] } })).violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => node.target) }));
  });
  expect(violations).toEqual([]);
}

function emailLink(email: string) {
  if (!existsSync(mailbox)) return "";
  for (const file of readdirSync(mailbox).filter(name => name.endsWith(".eml"))) {
    const content = readFileSync(path.join(mailbox, file), "utf8");
    if (!content.includes(`To: ${email}`)) continue;
    const link = content.match(/http:\/\/127\.0\.0\.1:3100\/reset-password#token=[A-Za-z0-9_-]{43}/)?.[0];
    if (link) return link;
  }
  return "";
}

test("forgot password sends a private email link, resets the password and revokes existing sessions", async ({ page, browser }, testInfo) => {
  page.setDefaultTimeout(10000);
  const email = `reset-${Date.now()}@example.com`;
  expect((await page.request.post("/api/v1/auth/register", { data: { email, password: originalPassword, full_name: "Synthetic Recovery Patient", role: "patient" } })).status()).toBe(201);
  const old = await browser.newContext({ baseURL: "http://127.0.0.1:3100" });
  try {
    expect((await old.request.post("/api/v1/auth/login", { data: { email, password: originalPassword } })).status()).toBe(200);
    await page.goto("/login");
    await page.getByRole("link", { name: "Forgot password?", exact: true }).click();
    await expect(page).toHaveURL(/\/forgot-password$/);
    await checkAccessibility(page);
    await page.getByLabel("Email Address", { exact: true }).fill(email);
    await page.getByRole("button", { name: "Send reset link", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Password reset requested", exact: true })).toBeVisible();
    await expect(page.locator("main").getByRole("status")).toContainText("It does not send them to your inbox.");
    await expect.poll(() => emailLink(email)).not.toBe("");
    const link = emailLink(email);
    await page.goto(link);
    await expect(page.getByRole("heading", { name: "Choose a new password", exact: true })).toBeVisible();
    await expect(page).toHaveURL(/\/reset-password$/);
    await checkAccessibility(page);
    await page.getByLabel("New password", { exact: true }).fill(newPassword);
    await page.getByLabel("Confirm new password", { exact: true }).fill("SyntheticMismatch123!");
    await page.getByRole("button", { name: "Reset password", exact: true }).click();
    await expect(page.locator("main").getByRole("alert")).toHaveText("Passwords do not match.");
    await page.getByLabel("Confirm new password", { exact: true }).fill(newPassword);
    await page.screenshot({ path: testInfo.outputPath("reset-password-desktop.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("reset-password-mobile.png"), fullPage: true });
    await page.getByRole("button", { name: "Reset password", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Password reset complete", exact: true })).toBeVisible();
    expect((await old.request.get("/api/v1/auth/me")).status()).toBe(401);
    expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401);
    expect((await page.request.post("/api/v1/auth/login", { data: { email, password: originalPassword } })).status()).toBe(401);
    await page.getByRole("link", { name: "Sign In", exact: true }).click();
    await page.getByLabel("Email Address", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(newPassword);
    await page.getByRole("button", { name: "Sign In", exact: true }).click();
    await expect(page.getByRole("region", { name: "Patient digital card", exact: true })).toBeVisible();
    await page.goto(link);
    await page.getByLabel("New password", { exact: true }).fill("SyntheticReplay123!");
    await page.getByLabel("Confirm new password", { exact: true }).fill("SyntheticReplay123!");
    await page.getByRole("button", { name: "Reset password", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Reset link unavailable", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Request a new reset link", exact: true })).toBeVisible();
  } finally { await old.close(); }
});

test("recovery screens support every language, unknown accounts and missing or unavailable links", async ({ page }, testInfo) => {
  page.setDefaultTimeout(10000);
  await page.goto("/forgot-password");
  await page.setViewportSize({ width: 390, height: 844 });
  for (const locale of ["hi", "kn", "te", "ta", "ml"]) {
    const catalog = JSON.parse(readFileSync(path.join(process.cwd(), "src/locales", `${locale}.json`), "utf8"));
    await page.locator("select").selectOption(locale);
    await expect(page.getByRole("heading", { name: catalog["Forgot your password?"], exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.goto("/reset-password");
    await expect(page.getByRole("heading", { name: catalog["Reset link unavailable"], exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: catalog["Request a new reset link"], exact: true })).toBeVisible();
    await page.goto("/forgot-password");
  }
  await page.screenshot({ path: testInfo.outputPath("forgot-password-malayalam-mobile.png"), fullPage: true });
  await page.locator("select").selectOption("en");
  await page.getByLabel("Email Address", { exact: true }).fill(`unknown-reset-${Date.now()}@example.com`);
  await page.getByRole("button", { name: "Send reset link", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Password reset requested", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Send another link", exact: true }).click();
  await page.route("**/api/v1/auth/forgot-password", route => route.fulfill({ status: 503, json: { detail: "Password recovery is unavailable. Please contact the service administrator." } }));
  await page.getByRole("button", { name: "Send reset link", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("Password recovery is unavailable.");
  await expect(page.getByRole("heading", { name: "Forgot your password?", exact: true })).toBeVisible();
  await checkAccessibility(page);
  await page.unroute("**/api/v1/auth/forgot-password");
  await page.route("**/api/v1/auth/forgot-password", route => route.fulfill({ status: 202, json: { message: "If an active account exists for this email, a password reset link will be sent.", delivery: "email" } }));
  await page.getByRole("button", { name: "Send reset link", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Check your email", exact: true })).toBeVisible();
  await expect(page.locator("main").getByRole("status")).toContainText("Check your inbox and spam folder.");
});
