import { test, expect, type Locator } from "@playwright/test";
import { openSection } from "./navigation";

test.use({ reducedMotion: "reduce" });

async function expectDestination(target: Locator) {
  await expect(target).toBeFocused();
  await expect.poll(() => target.evaluate((element) => {
    const bounds = element.getBoundingClientRect();
    return bounds.top >= 0 && bounds.top < window.innerHeight;
  })).toBe(true);
}

test("detail and history buttons move the viewport and keyboard focus to their data", async ({ page }) => {
  const email = `synthetic-detail-${Date.now()}@example.com`;
  expect((await page.request.post("/api/v1/auth/register", { data: {
    email, password: "SyntheticDetail123!", full_name: "Synthetic Detail Patient", role: "patient",
  } })).status()).toBe(201);
  expect((await page.request.post("/api/v1/auth/login", { data: { email, password: "SyntheticDetail123!" } })).status()).toBe(200);
  const me = await (await page.request.get("/api/v1/auth/me")).json();
  expect((await page.request.post("/api/v1/clinical/encounters", { data: {
    patient_id: me.patient.id, title: "Synthetic navigation consultation",
    notes: "Synthetic notes for detail navigation.", occurred_on: "2026-01-10",
  } })).status()).toBe(201);
  await page.goto("/dashboard");
  for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await openSection(page, "consultations");
    const clinical = page.getByRole("region", { name: "Medical timeline and follow-ups", exact: true });
    await clinical.getByRole("button", { name: "Synthetic navigation consultation", exact: true }).click();
    const selected = clinical.getByRole("article", { name: "Selected consultation", exact: true });
    await expectDestination(selected);
    await selected.getByRole("button", { name: "Consultation history", exact: true }).click();
    const history = clinical.getByRole("region", { name: "Consultation version history", exact: true });
    await expectDestination(history);
    await expect(history).toContainText("Synthetic notes for detail navigation.");
    await history.getByRole("button", { name: "Close history", exact: true }).click();
    await selected.getByRole("button", { name: "Correct consultation", exact: true }).click();
    const editor = clinical.getByRole("form", { name: "Correct consultation", exact: true });
    await expectDestination(editor);
    await editor.getByRole("button", { name: "Cancel", exact: true }).click();
    await selected.getByRole("button", { name: "Close consultation", exact: true }).click();
  }
});
