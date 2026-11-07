import { test, expect, type APIRequestContext, type Route } from "@playwright/test";
import { openSection } from "./navigation";

test("patient switching cancels stale documents and refreshed revocation clears the context", async ({ page, browser }) => {
  test.setTimeout(90000);
  const password = "SyntheticContext123!";
  const stamp = Date.now();
  const second = await browser.newContext({ baseURL: "http://127.0.0.1:3100" });
  const doctor = await browser.newContext({ baseURL: "http://127.0.0.1:3100" });
  const admin = await browser.newContext({ baseURL: "http://127.0.0.1:3100" });
  async function patient(client: APIRequestContext, suffix: string) {
    const email = `synthetic-context-${suffix}-${stamp}@example.com`;
    expect((await client.post("/api/v1/auth/register", { data: { email, password, full_name: `Synthetic Context ${suffix}`, role: "patient" } })).status()).toBe(201);
    await client.post("/api/v1/auth/login", { data: { email, password } });
    const me = await (await client.get("/api/v1/auth/me")).json();
    const response = await client.post("/api/v1/documents/upload", { multipart: { title: `Synthetic record ${suffix}`, document_type: "prescription", file: { name: `synthetic-${suffix}.png`, mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAALElEQVR4nGP8//8/A7mAiWydDKOaSQZMpGtBgFHNJAImUjUgg1HNJAKKAgwAnKADJa4TmNgAAAAASUVORK5CYII=", "base64") } } });
    expect(response.status()).toBe(201);
    return { id: me.patient.id as string, doc: (await response.json()).document };
  }
  try {
    const a = await patient(page.request, "A");
    const b = await patient(second.request, "B");
    const doctorEmail = `synthetic-context-doctor-${stamp}@example.com`;
    expect((await doctor.request.post("/api/v1/auth/register", { data: { email: doctorEmail, password, full_name: "Synthetic Context Doctor", role: "doctor", license_number: `SYNTHETIC-${stamp}`, specialization: "Synthetic context review" } })).status()).toBe(201);
    await doctor.request.post("/api/v1/auth/login", { data: { email: doctorEmail, password } });
    const doctorMe = await (await doctor.request.get("/api/v1/auth/me")).json();
    await admin.request.post("/api/v1/auth/login", { data: { email: "synthetic-admin@example.com", password: "SyntheticAdminBrowser123!" } });
    expect((await admin.request.post(`/api/v1/admin/doctors/${doctorMe.doctor.id}/verification`, { data: { status: "verified", evidence_reference: "Synthetic patient context regression fixture" } })).status()).toBe(200);
    for (const [owner, request] of [[a, page.request], [b, second.request]] as const) {
      const response = await doctor.request.post("/api/v1/consent/requests", { data: { patient_id: owner.id, scope: "all", purpose: "Synthetic patient context regression", duration_hours: 24, include_clinical_records: true, allow_clinical_write: true } });
      expect(response.status()).toBe(201);
      expect((await request.post(`/api/v1/consent/requests/${(await response.json()).id}/decision`, { data: { decision: "approve" } })).status()).toBe(200);
    }
    const clinician = await doctor.newPage();
    clinician.setDefaultTimeout(10000);
    let held: Route | undefined;
    let intercepted: (() => void) | undefined;
    let holdFirstA = true;
    const started = new Promise<void>(resolve => { intercepted = resolve; });
    await clinician.route("**/api/v1/documents?*", route => {
      if (holdFirstA && new URL(route.request().url()).searchParams.get("patient_id") === a.id) {
        holdFirstA = false;
        held = route;
        intercepted?.();
      } else return route.continue();
    });
    await clinician.goto("/dashboard#documents");
    const picker = clinician.getByLabel("Select a patient");
    await picker.selectOption(a.id);
    await started;
    const cancelled = clinician.waitForEvent("requestfailed", { predicate: request => request.url().includes(`patient_id=${a.id}`) });
    await picker.selectOption(b.id);
    await cancelled;
    await expect(clinician.getByRole("heading", { name: "Synthetic record B", exact: true })).toBeVisible();
    await held!.fulfill({ status: 200, json: [a.doc] });
    await expect(clinician.getByRole("heading", { name: "Synthetic record A", exact: true })).toHaveCount(0);
    await expect(clinician.getByRole("heading", { name: "Synthetic record B", exact: true })).toBeVisible();
    await openSection(clinician, "consultations");
    await clinician.getByRole("button", { name: "Add consultation", exact: true }).click();
    const editor = clinician.getByRole("form", { name: "New consultation", exact: true });
    await expect(editor.getByText("Synthetic record B", { exact: false })).toBeVisible();
    await expect(editor.getByText("Synthetic record A", { exact: false })).toHaveCount(0);
    await openSection(clinician, "documents");
    const grants = await (await second.request.get("/api/v1/consent/grants")).json();
    expect((await second.request.post(`/api/v1/consent/grants/${grants[0].id}/revoke`)).status()).toBe(204);
    await clinician.getByRole("button", { name: "Refresh records", exact: true }).click();
    await expect(picker).toHaveValue("");
    await expect(clinician.getByRole("heading", { name: "Synthetic record B", exact: true })).toHaveCount(0);
    expect((await doctor.request.get(`/api/v1/documents/${b.doc.id}/download`)).status()).toBe(403);
    await picker.selectOption(a.id);
    await expect(clinician.getByRole("heading", { name: "Synthetic record A", exact: true })).toBeVisible();
    await clinician.route("**/api/v1/documents?*", route => route.fulfill({ status: 403, json: { detail: "Document unavailable or access no longer permitted." } }));
    await clinician.getByRole("button", { name: "Refresh records", exact: true }).click();
    const workspace = clinician.getByRole("region", { name: "Care workspace", exact: true });
    await expect(workspace.getByRole("alert")).toContainText("Document unavailable or access no longer permitted.");
    await expect(clinician.getByRole("heading", { name: "Synthetic record A", exact: true })).toHaveCount(0);
    await picker.selectOption("");
    await expect(workspace.getByRole("alert")).toHaveCount(0);
  } finally { await second.close(); await doctor.close(); await admin.close(); }
});

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
    await expect(page.locator('#workspace-navigation a[aria-current="page"]')).toHaveAttribute("href", `#${id}`);
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

test("patient and verified doctor screens fit desktop, tablet and mobile", async ({ page, browser }, testInfo) => {
  test.setTimeout(240000);
  page.setDefaultTimeout(10000);
  const stamp = Date.now();
  const password = "SyntheticPolish123!";
  const email = `synthetic-polish-patient-${stamp}@example.com`;
  expect((await page.request.post("/api/v1/auth/register", { data: { email, password, full_name: "Synthetic Patient With A Longer Family Name", role: "patient" } })).status()).toBe(201);
  await page.request.post("/api/v1/auth/login", { data: { email, password } });
  const me = await (await page.request.get("/api/v1/auth/me")).json();
  const source = await page.request.post("/api/v1/documents/upload", { multipart: { title: "Synthetic prescription from a longer clinic name for responsive review", document_type: "prescription", file: { name: "synthetic-prescription-original-with-a-longer-filename.png", mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAALElEQVR4nGP8//8/A7mAiWydDKOaSQZMpGtBgFHNJAImUjUgg1HNJAKKAgwAnKADJa4TmNgAAAAASUVORK5CYII=", "base64") } } });
  expect(source.status()).toBe(201);
  const doc = (await source.json()).document;
  const created = await page.request.post("/api/v1/clinical/encounters", { data: { patient_id: me.patient.id, title: "Synthetic consultation for a detailed source review", notes: "Synthetic patient account. This is a browser layout fixture, not clinical advice.", occurred_on: "2026-01-10", source_document_ids: [doc.id] } });
  expect(created.status()).toBe(201);
  const encounter = await created.json();
  expect((await page.request.post("/api/v1/clinical/follow-ups", { data: { encounter_id: encounter.id, title: "Synthetic follow-up with a longer description to check wrapping", due_on: "2027-01-10" } })).status()).toBe(201);
  const doctor = await browser.newContext({ baseURL: "http://127.0.0.1:3100" });
  const admin = await browser.newContext({ baseURL: "http://127.0.0.1:3100" });
  try {
    const doctorEmail = `synthetic-polish-doctor-${stamp}@example.com`;
    expect((await doctor.request.post("/api/v1/auth/register", { data: { email: doctorEmail, password, full_name: "Synthetic Verified Review Doctor", role: "doctor", license_number: `SYNTHETIC-POLISH-${stamp}`, specialization: "Synthetic verification" } })).status()).toBe(201);
    await doctor.request.post("/api/v1/auth/login", { data: { email: doctorEmail, password } });
    const doctorMe = await (await doctor.request.get("/api/v1/auth/me")).json();
    await admin.request.post("/api/v1/auth/login", { data: { email: "synthetic-admin@example.com", password: "SyntheticAdminBrowser123!" } });
    expect((await admin.request.post(`/api/v1/admin/doctors/${doctorMe.doctor.id}/verification`, { data: { status: "verified", evidence_reference: "Synthetic responsive review fixture; not a real professional" } })).status()).toBe(200);
    const consent = await doctor.request.post("/api/v1/consent/requests", { data: { patient_id: me.patient.id, scope: "all", purpose: "Synthetic patient-authorized responsive review", duration_hours: 24, include_clinical_records: true, allow_clinical_write: true } });
    expect(consent.status()).toBe(201);
    expect((await page.request.post(`/api/v1/consent/requests/${(await consent.json()).id}/decision`, { data: { decision: "approve" } })).status()).toBe(200);
    const pending = await doctor.request.post("/api/v1/consent/requests", { data: { patient_id: me.patient.id, scope: "prescriptions_only", purpose: "Synthetic additional pending request for consent layout", duration_hours: 2 } });
    expect(pending.status()).toBe(201);
    await expect.poll(async () => (await (await page.request.get(`/api/v1/documents/${doc.id}/processing`)).json()).status, { timeout: 20000 }).toBe("succeeded");
    expect((await doctor.request.post(`/api/v1/documents/${doc.id}/review`, { data: { expected_version: 0, expected_attempt: 1, reviewed_text: "Medicine: SYNTHETIC-POLISH | Strength: 10 synthetic units | Dose: 1 synthetic unit | Frequency: nightly", reason: "Synthetic original checked for browser layout review", source_checked: true } })).status()).toBe(201);
    expect((await doctor.request.post(`/api/v1/documents/${doc.id}/prescription/generate`, { data: { expected_version: 0, source_review_version: 1 } })).status()).toBe(201);
    expect((await page.request.post("/api/v1/clinical/medication-use", { data: { patient_id: me.patient.id, name: "SYNTHETIC-POLISH reported medication", use_status: "unknown", reported_on: "2026-01-10", reason: "Synthetic reported account for responsive browser review" } })).status()).toBe(201);
    const clinicianPage = await doctor.newPage();
    clinicianPage.setDefaultTimeout(10000);
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    clinicianPage.on("pageerror", error => errors.push(error.message));
    await page.goto("/dashboard");
    await clinicianPage.goto("/dashboard#patients");
    await clinicianPage.getByLabel("Select a patient").selectOption(me.patient.id);
    const patientSections = ["overview", "documents", "timeline", "consultations", "medications", "records", "care", "sharing", "profile", "privacy"];
    const doctorSections = ["patients", "documents", "timeline", "consultations", "medications", "records", "care"];
    const coverage: { role: string; section: string; viewport: string }[] = [];
    for (const [size, viewport] of Object.entries({ desktop: { width: 1440, height: 1000 }, tablet: { width: 820, height: 1180 }, mobile: { width: 390, height: 844 } })) {
      for (const [role, target, sections] of [["patient", page, patientSections], ["doctor", clinicianPage, doctorSections]] as const) {
        await target.setViewportSize(viewport);
        for (const section of sections) {
          await openSection(target, section);
          await expect(target.locator("main h1")).toBeVisible();
          await expect.poll(() => target.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
          if (viewport.width < 1024) {
            const gap = await target.evaluate(() => document.querySelector("main h1")!.getBoundingClientRect().top - document.querySelector(".workspace-sidebar")!.getBoundingClientRect().bottom);
            expect(gap).toBeLessThan(140);
          }
          await target.screenshot({ path: testInfo.outputPath(`${role}-${size}-${section}.png`), fullPage: true, animations: "disabled" });
          coverage.push({ role, section, viewport: size });
        }
        await openSection(target, "documents");
        await target.getByRole("button", { name: "Show processing", exact: true }).click();
        await expect(target.getByRole("region", { name: "Document processing", exact: true })).toBeVisible();
        await expect(target.getByRole("region", { name: "Structured prescription draft", exact: true })).toBeVisible();
        await expect(target.getByRole("article", { name: "Prescription row 1", exact: true })).toBeVisible();
        expect(await target.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await target.screenshot({ path: testInfo.outputPath(`${role}-${size}-prescription-review.png`), fullPage: true, animations: "disabled" });
        await target.getByRole("button", { name: "Hide processing", exact: true }).click();
        await openSection(target, "timeline");
        const timeline = target.getByRole("region", { name: "Unified medical timeline", exact: true });
        const sourceButton = timeline.locator("button.timeline-event").first();
        await sourceButton.click();
        await expect(sourceButton).toHaveAttribute("aria-expanded", "true");
        await timeline.getByRole("button", { name: "Close timeline source", exact: true }).click();
        await expect(sourceButton).toBeFocused();
        await openSection(target, "documents");
        if (role === "patient") {
          await target.getByRole("button", { name: "Upload Document", exact: true }).click();
          await expect(target.getByRole("dialog")).toBeVisible();
          await expect(target.getByRole("button", { name: "Click to select file", exact: true })).toBeFocused();
          expect(await target.evaluate(() => document.body.style.overflow)).toBe("hidden");
          await target.screenshot({ path: testInfo.outputPath(`${role}-${size}-upload.png`), fullPage: true, animations: "disabled" });
          await target.keyboard.press("Escape");
          await expect(target.getByRole("button", { name: "Upload Document", exact: true })).toBeFocused();
        }
        await openSection(target, "medications");
        const medication = target.getByRole("region", { name: "Medication use and reconciliation", exact: true });
        await medication.getByRole("button", { name: /SYNTHETIC-POLISH reported medication/ }).click();
        if (role === "doctor") {
          await medication.getByRole("button", { name: "Reconcile medication report", exact: true }).click();
          await expect(medication.getByRole("form", { name: "Reconcile medication report", exact: true })).toBeVisible();
        }
        expect(await target.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await target.screenshot({ path: testInfo.outputPath(`${role}-${size}-medication-review.png`), fullPage: true, animations: "disabled" });
        if (role === "doctor") await medication.getByRole("form", { name: "Reconcile medication report", exact: true }).getByRole("button", { name: "Cancel reconciliation", exact: true }).click();
        await medication.getByRole("button", { name: "Close medication report", exact: true }).click();
        if (role === "doctor") {
          await openSection(target, "patients");
          const search = target.getByRole("searchbox", { name: "Authorized patients", exact: true });
          await search.fill("NoMatchingSyntheticName");
          await expect(target.getByText("No patients match your search.", { exact: true })).toBeVisible();
          await openSection(target, "documents");
          await expect(target.getByText("No patients match your search.", { exact: true })).toBeHidden();
          await openSection(target, "patients");
          await search.fill("");
        } else {
          await openSection(target, "documents");
          await target.getByRole("searchbox", { name: "Search records...", exact: true }).fill("NoMatchingSyntheticDocument");
          await target.getByRole("button", { name: "Clear filters", exact: true }).click();
          await expect(target.locator(`[data-document-id="${doc.id}"]`)).toBeVisible();
          await openSection(target, "sharing");
          const history = target.locator("details").filter({ has: target.locator("summary", { hasText: "Record access history" }) });
          await history.locator("summary").click();
          await expect(history.getByRole("table")).toBeVisible();
          await history.locator("summary").click();
        }
      }
    }
    expect(errors).toEqual([]);
    expect(coverage).toHaveLength(51);
    await testInfo.attach("responsive-coverage", { body: JSON.stringify({ mode: "synthetic_local_browser", screens: coverage, consoleErrors: errors }), contentType: "application/json" });
  } finally { await doctor.close(); await admin.close(); }
});

test("a patient can upload from home, recover from an invalid file, find the saved record and open a follow-up on mobile", async ({ page }, testInfo) => {
  const email = `synthetic-journey-${Date.now()}@example.com`;
  expect((await page.request.post("/api/v1/auth/register", { data: { email, password: "SyntheticJourney123!", full_name: "Synthetic Journey Patient", role: "patient" } })).status()).toBe(201);
  await page.request.post("/api/v1/auth/login", { data: { email, password: "SyntheticJourney123!" } });
  const me = await (await page.request.get("/api/v1/auth/me")).json();
  const encounterResponse = await page.request.post("/api/v1/clinical/encounters", { data: { patient_id: me.patient.id, title: "Synthetic journey consultation", notes: "Synthetic source", occurred_on: "2026-01-10" } });
  expect(encounterResponse.status()).toBe(201);
  const encounter = await encounterResponse.json();
  const followResponse = await page.request.post("/api/v1/clinical/follow-ups", { data: { encounter_id: encounter.id, title: "Synthetic next follow-up", due_on: "2027-01-10" } });
  expect(followResponse.status()).toBe(201);
  const follow = await followResponse.json();
  await page.goto("/dashboard");
  await expect(page.getByRole("region", { name: "Next follow-ups", exact: true })).toContainText("Synthetic next follow-up");
  await page.screenshot({ path: testInfo.outputPath("patient-home-desktop.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath("patient-home-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "Upload prescription", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator('input[type="file"]').setInputFiles({ name: "invalid.txt", mimeType: "text/plain", buffer: Buffer.from("synthetic invalid input") });
  await expect(dialog.getByRole("alert")).toContainText("Choose a PDF, PNG or JPG file.");
  await expect(dialog.getByRole("button", { name: "Upload Document", exact: true })).toBeDisabled();
  const bytes = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAIAAAAC64paAAAALElEQVR4nGP8//8/A7mAiWydDKOaSQZMpGtBgFHNJAImUjUgg1HNJAKKAgwAnKADJa4TmNgAAAAASUVORK5CYII=", "base64");
  const transfer = await page.evaluateHandle((data) => {
    const value = new DataTransfer();
    value.items.add(new File([new Uint8Array(data)], "synthetic-journey.png", { type: "image/png" }));
    return value;
  }, Array.from(bytes));
  await dialog.locator(".upload-dropzone").dispatchEvent("drop", { dataTransfer: transfer });
  await expect(dialog.getByRole("img", { name: "Selected document preview", exact: true })).toBeVisible();
  await dialog.getByLabel("Document Title", { exact: true }).fill("Synthetic journey prescription");
  await page.screenshot({ path: testInfo.outputPath("upload-preview-mobile.png"), fullPage: true });
  let rejectUpload: (() => Promise<void>) | undefined;
  let uploadStarted: (() => void) | undefined;
  const intercepted = new Promise<void>(resolve => { uploadStarted = resolve; });
  await page.route("**/api/v1/documents/upload", async route => {
    rejectUpload = () => route.fulfill({ status: 503, json: { detail: "Synthetic temporary upload failure" } });
    uploadStarted?.();
  }, { times: 1 });
  await dialog.getByRole("button", { name: "Upload Document", exact: true }).click();
  await intercepted;
  await expect(dialog.locator("form")).toHaveAttribute("aria-busy", "true");
  await page.keyboard.press("Tab");
  expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
  await rejectUpload!();
  await expect(dialog.getByRole("alert")).toContainText("Synthetic temporary upload failure");
  await expect(dialog.getByLabel("Document Title", { exact: true })).toHaveValue("Synthetic journey prescription");
  await dialog.getByRole("button", { name: "Upload Document", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page).toHaveURL(/#documents$/);
  await expect(page.getByRole("region", { name: "Document processing", exact: true })).toBeVisible();
  await page.locator('.patient-mobile-navigation a[href="#overview"]').click();
  await page.getByRole("region", { name: "Recent records", exact: true }).getByRole("button", { name: /Synthetic journey prescription/ }).click();
  await expect(page).toHaveURL(/#documents$/);
  await expect(page.getByRole("heading", { name: "Synthetic journey prescription", exact: true })).toBeVisible();
  await page.locator('.patient-mobile-navigation a[href="#overview"]').click();
  await page.getByRole("region", { name: "Next follow-ups", exact: true }).getByRole("button", { name: /Synthetic next follow-up/ }).click();
  await expect(page.locator(`[data-follow-up-id="${follow.id}"]`)).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
