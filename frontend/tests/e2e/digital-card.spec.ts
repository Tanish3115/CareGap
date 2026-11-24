import { test, expect, type APIRequestContext, type Download, type Locator, type Page, type Route, type TestInfo } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";

const password = "SyntheticCardBrowser123!";

async function expectVisitingCard(card: Locator, inHeader = true) {
  const bounds = await card.locator("[data-digital-card-face]").evaluate(element => {
    const face = element.getBoundingClientRect();
    const main = element.closest("main")!;
    const mainBox = main.getBoundingClientRect();
    const heading = main.querySelector("h1")!.getBoundingClientRect();
    return { width: face.width, height: face.height, rightGap: mainBox.right - Number.parseFloat(getComputedStyle(main).paddingRight) - face.right,
      top: face.top, headingTop: heading.top, desktop: innerWidth >= 768,
      fieldsFit: [...element.querySelectorAll("dd")].every(field => field.getBoundingClientRect().bottom <= face.bottom - 1) };
  });
  expect(bounds.width).toBeLessThanOrEqual(337);
  expect(bounds.width / bounds.height).toBeCloseTo(1.75, 2);
  expect(Math.abs(bounds.rightGap)).toBeLessThan(2);
  expect(bounds.fieldsFit).toBe(true);
  if (inHeader && bounds.desktop) expect(bounds.top).toBeLessThanOrEqual(bounds.headingTop);
}

async function downloadCard(card: Locator, page: Page, testInfo: TestInfo, expected: string, artifact: string, label = "Download card") {
  const pending = page.waitForEvent("download");
  await card.getByRole("button", { name: label, exact: true }).click();
  const download = await pending;
  expect(download.suggestedFilename()).toBe(expected);
  const filename = testInfo.outputPath(artifact);
  await download.saveAs(filename);
  const python = path.resolve(process.platform === "win32" ? "../backend/.venv/Scripts/python.exe" : "../backend/.venv/bin/python");
  const inspected = JSON.parse(execFileSync(python, ["-c", "import json,sys; from PIL import Image; image=Image.open(sys.argv[1]); info={'size':list(image.size),'dpi':image.info.get('dpi')}; image.verify(); print(json.dumps(info))", filename], { encoding: "utf8" }));
  expect(inspected.size).toEqual([1050, 600]);
  expect(inspected.dpi[0]).toBeCloseTo(300, 1);
  expect(inspected.dpi[1]).toBeCloseTo(300, 1);
}

test("patient card appears on login, copies the ID, and stays current after profile edits", async ({ page, context }, testInfo) => {
  page.setDefaultTimeout(10000);
  const email = `synthetic-card-patient-${Date.now()}@example.com`;
  expect((await page.request.post("/api/v1/auth/register", { data: {
    email, password, full_name: "Synthetic Digital Card Patient", role: "patient",
  } })).status()).toBe(201);
  await page.goto("/login");
  await page.getByLabel("Email Address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page).toHaveURL(/dashboard/);
  const card = page.getByRole("region", { name: "Patient digital card", exact: true });
  await expect(card).toBeVisible();
  await expectVisitingCard(card);
  await expect(card.getByRole("heading", { name: "Synthetic Digital Card Patient", exact: true })).toBeVisible();
  await expect(card.getByText("Not recorded", { exact: true })).toHaveCount(4);
  const me = await (await page.request.get("/api/v1/auth/me")).json();
  await expect(card.getByText(me.patient.patient_code, { exact: true })).toBeVisible();
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await card.getByRole("button", { name: "Copy patient ID", exact: true }).click();
  await expect(card.getByRole("status")).toHaveText("Patient ID copied.");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(me.patient.patient_code);
  await card.getByRole("link", { name: "Edit your health profile", exact: true }).click();
  await expect(page).toHaveURL(/#profile$/);
  await page.getByLabel("Date of birth", { exact: true }).fill("1994-05-12");
  await page.getByRole("combobox", { name: "Blood group", exact: true }).selectOption("O+");
  await page.getByLabel("Emergency contact", { exact: true }).fill("Synthetic contact +10000000001");
  await page.getByRole("button", { name: "Save profile", exact: true }).click();
  await expect(card.getByText("O+", { exact: true })).toBeVisible();
  await expect(card.getByText("Synthetic contact +10000000001", { exact: true })).toBeVisible();
  await page.reload();
  await expect(card.getByText("O+", { exact: true })).toBeVisible();
  await downloadCard(card, page, testInfo, `caregap-patient-${me.patient.patient_code}.png`, "patient-card-download.png");
  for (const locale of ["hi", "kn", "te", "ta", "ml"]) {
    const catalog = JSON.parse(readFileSync(path.join(process.cwd(), "src/locales", `${locale}.json`), "utf8"));
    await page.locator("select").first().selectOption(locale);
    const translated = page.getByRole("region", { name: catalog["Patient digital card"], exact: true });
    await expect(translated.getByText(me.patient.patient_code, { exact: true })).toBeVisible();
    await expect(translated.getByRole("button", { name: catalog["Copy patient ID"], exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expectVisitingCard(translated);
    if (locale === "ml") await downloadCard(translated, page, testInfo, `caregap-patient-${me.patient.patient_code}.png`, "patient-card-download-malayalam.png", catalog["Download card"]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.locator("select").first().selectOption("en");
  await page.setViewportSize({ width: 320, height: 740 });
  await expectVisitingCard(card);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await card.screenshot({ path: testInfo.outputPath("patient-card-mobile.png") });
  await page.setViewportSize({ width: 1280, height: 900 });
  await card.screenshot({ path: testInfo.outputPath("patient-card-desktop.png") });
  await page.screenshot({ path: testInfo.outputPath("patient-card-corner-desktop.png"), fullPage: true });
});

test("doctor card shows verification and authorized patient cards clear on switching or revocation", async ({ page, browser }, testInfo) => {
  test.setTimeout(90000);
  page.setDefaultTimeout(10000);
  const stamp = Date.now();
  const first = await browser.newContext({ baseURL: "http://127.0.0.1:3100" });
  const second = await browser.newContext({ baseURL: "http://127.0.0.1:3100" });
  const admin = await browser.newContext({ baseURL: "http://127.0.0.1:3100" });
  async function patient(client: APIRequestContext, suffix: string) {
    const email = `synthetic-digital-card-${suffix}-${stamp}@example.com`;
    expect((await client.post("/api/v1/auth/register", { data: {
      email, password, full_name: `Synthetic Card ${suffix}`, role: "patient",
    } })).status()).toBe(201);
    expect((await client.post("/api/v1/auth/login", { data: { email, password } })).status()).toBe(200);
    const me = await (await client.get("/api/v1/auth/me")).json();
    return { id: me.patient.id as string, patient_code: me.patient.patient_code as string, full_name: me.full_name as string };
  }
  try {
    const a = await patient(first.request, "A");
    const b = await patient(second.request, "B");
    const email = `synthetic-digital-card-doctor-${stamp}@example.com`;
    const license = `SYNTHETIC-CARD-${stamp}`;
    expect((await page.request.post("/api/v1/auth/register", { data: {
      email, password, full_name: "Synthetic Card Doctor", role: "doctor", license_number: license,
      specialization: "Synthetic specialty", hospital_affiliation: "Synthetic Clinic",
    } })).status()).toBe(201);
    await page.goto("/login");
    await page.getByLabel("Email Address", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign In", exact: true }).click();
    const doctorCard = page.getByRole("region", { name: "Doctor digital card", exact: true });
    await expect(doctorCard).toBeVisible();
    await expectVisitingCard(doctorCard);
    await expect(doctorCard).toContainText(license);
    await expect(doctorCard).toContainText("Synthetic specialty");
    await expect(doctorCard).toContainText("Synthetic Clinic");
    await expect(doctorCard).toContainText("Verification status: pending");
    await downloadCard(doctorCard, page, testInfo, "caregap-doctor-card.png", "pending-doctor-card-download.png");
    await expect(page.getByText("Professional verification required", { exact: true })).toBeVisible();
    const doctor = await (await page.request.get("/api/v1/auth/me")).json();
    await admin.request.post("/api/v1/auth/login", { data: {
      email: "synthetic-admin@example.com", password: "SyntheticAdminBrowser123!",
    } });
    expect((await admin.request.post(`/api/v1/admin/doctors/${doctor.doctor.id}/verification`, { data: {
      status: "verified", evidence_reference: "Synthetic digital card browser verification",
    } })).status()).toBe(200);
    expect((await page.request.get(`/api/v1/patients/${a.id}/card`)).status()).toBe(403);
    for (const [owner, request] of [[a, first.request], [b, second.request]] as const) {
      const response = await page.request.post("/api/v1/consent/requests", { data: {
        patient_id: owner.id, scope: "prescriptions_only", purpose: "Synthetic card access test", duration_hours: 24,
      } });
      expect(response.status()).toBe(201);
      expect((await request.post(`/api/v1/consent/requests/${(await response.json()).id}/decision`, { data: { decision: "approve" } })).status()).toBe(200);
    }
    await page.reload();
    await expect(doctorCard).toContainText("Verification status: verified");
    let held: Route | undefined;
    let start: (() => void) | undefined;
    const started = new Promise<void>(resolve => { start = resolve; });
    await page.route(`**/api/v1/patients/${a.id}/card`, route => { held = route; start?.(); });
    const picker = page.getByRole("combobox", { name: "Select a patient", exact: true });
    await picker.selectOption(a.id);
    await started;
    const cancelled = page.waitForEvent("requestfailed", { predicate: request => request.url().endsWith(`/patients/${a.id}/card`) });
    await picker.selectOption(b.id);
    await cancelled;
    const shared = page.getByRole("region", { name: "Patient digital card", exact: true });
    await expect(shared).toContainText(b.full_name);
    await held!.fulfill({ status: 200, json: a });
    await expect(shared).toContainText(b.patient_code);
    await expect(shared).not.toContainText(a.full_name);
    await expectVisitingCard(shared, false);
    await downloadCard(shared, page, testInfo, `caregap-patient-${b.patient_code}.png`, "shared-patient-card-download.png");
    await downloadCard(doctorCard, page, testInfo, "caregap-doctor-card.png", "verified-doctor-card-download.png");
    const lateDownloads: string[] = [];
    const recordLateDownload = (download: Download) => lateDownloads.push(download.suggestedFilename());
    page.on("download", recordLateDownload);
    let heldExport: Route | undefined;
    let exportStarted: (() => void) | undefined;
    const exportRequest = new Promise<void>(resolve => { exportStarted = resolve; });
    await page.route(`**/api/v1/patients/${b.id}/card`, route => { heldExport = route; exportStarted?.(); });
    await shared.getByRole("button", { name: "Download card", exact: true }).click();
    await exportRequest;
    const cancelledExport = page.waitForEvent("requestfailed", { predicate: request => request.url().endsWith(`/patients/${b.id}/card`) });
    await picker.selectOption("");
    await cancelledExport;
    await heldExport!.fulfill({ status: 200, json: b });
    await expect(shared).toHaveCount(0);
    expect(lateDownloads).toEqual([]);
    page.off("download", recordLateDownload);
    await page.unroute(`**/api/v1/patients/${b.id}/card`);
    await picker.selectOption(b.id);
    await expect(shared).toContainText(b.full_name);
    await expect(shared.getByText("Emergency contact", { exact: true })).toHaveCount(0);
    await shared.getByRole("link", { name: "View shared records", exact: true }).click();
    await expect(page).toHaveURL(/#documents$/);
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await doctorCard.screenshot({ path: testInfo.outputPath("doctor-card-mobile.png") });
    await shared.screenshot({ path: testInfo.outputPath("shared-patient-card-mobile.png") });
    const grants = await (await second.request.get("/api/v1/consent/grants")).json();
    expect((await second.request.post(`/api/v1/consent/grants/${grants[0].id}/revoke`)).status()).toBe(204);
    const deniedDownloads: string[] = [];
    page.on("download", download => deniedDownloads.push(download.suggestedFilename()));
    await shared.getByRole("button", { name: "Download card", exact: true }).click();
    await expect(shared.getByRole("alert")).toHaveText("Card unavailable. Refresh your account and try again.");
    expect(deniedDownloads).toEqual([]);
    await page.getByRole("button", { name: "Refresh records", exact: true }).click();
    await expect(picker).toHaveValue("");
    await expect(shared).toHaveCount(0);
    expect((await page.request.get(`/api/v1/patients/${b.id}/card`)).status()).toBe(403);
    await page.unroute(`**/api/v1/patients/${a.id}/card`);
    await page.route(`**/api/v1/patients/${a.id}/card`, route => route.fulfill({ status: 403, json: { detail: "Access denied" } }));
    await picker.selectOption(a.id);
    await expect(page.getByRole("region", { name: "Care workspace", exact: true }).getByRole("alert"))
      .toContainText("Patient card unavailable. Refresh patient access.");
    await expect(shared).toHaveCount(0);
    expect((await admin.request.post(`/api/v1/admin/doctors/${doctor.doctor.id}/verification`, { data: {
      status: "rejected", evidence_reference: "Synthetic rejected card verification test",
    } })).status()).toBe(200);
    await page.reload();
    await expect(doctorCard).toContainText("Verification status: rejected");
    await expect(shared).toHaveCount(0);
  } finally {
    await first.close(); await second.close(); await admin.close();
  }
});
