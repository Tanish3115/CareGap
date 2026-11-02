import { test, expect } from "@playwright/test";
import { writeFileSync } from "node:fs";

test("bounded concurrent timeline reads preserve pagination and patient isolation", async ({ request }, testInfo) => {
  test.setTimeout(120000);
  const email = `synthetic-load-${Date.now()}@example.com`;
  const signup = await request.post("/api/v1/auth/register", { data: {
    email, password: "SyntheticLoadBrowser123!", full_name: "Synthetic Load Patient", role: "patient",
  } });
  expect(signup.status()).toBe(201);
  expect((await request.post("/api/v1/auth/login", { data: { email, password: "SyntheticLoadBrowser123!" } })).status()).toBe(200);
  const profile = await request.get("/api/v1/patients/me");
  expect(profile.ok()).toBe(true);
  const patient = await profile.json();
  for (let index = 0; index < 40; index++) {
    const response = await request.post("/api/v1/clinical/encounters", { data: { patient_id: patient.id,
      occurred_on: "2025-01-01", title: `Synthetic load consultation ${index}`, notes: "Synthetic load fixture only.", source_document_ids: [] } });
    expect(response.status()).toBe(201);
  }
  const durations: number[] = [];
  const started = Date.now();
  for (let batch = 0; batch < 10; batch++) {
    await Promise.all(Array.from({ length: 6 }, async (_, index) => {
      const before = Date.now();
      const response = await request.get(`/api/v1/clinical/unified-timeline?patient_id=${patient.id}&limit=10&offset=${(index % 4)*10}`);
      durations.push(Date.now()-before);
      expect(response.status()).toBe(200);
      const body = await response.json();
      const rows = Array.isArray(body) ? body : body.items;
      expect(rows).toHaveLength(10);
      expect(new Set(rows.map((row: { id: string }) => row.id)).size).toBe(10);
    }));
  }
  const denied = await request.get("/api/v1/clinical/unified-timeline?patient_id=00000000-0000-4000-8000-000000000001&limit=10");
  expect(denied.status()).toBe(403);
  durations.sort((left, right) => left-right);
  const report = { mode: "isolated_synthetic_smoke", consultations: 40, requests: durations.length, concurrency: 6,
    p50_ms: durations[Math.floor(durations.length*0.5)], p95_ms: durations[Math.floor(durations.length*0.95)],
    max_ms: durations.at(-1), elapsed_ms: Date.now()-started, production_capacity_validated: false };
  writeFileSync(testInfo.outputPath("bounded-load.json"), JSON.stringify(report, null, 2));
  await testInfo.attach("bounded-load.json", { body: JSON.stringify(report, null, 2), contentType: "application/json" });
  expect(report.p95_ms).toBeLessThan(10000);
});
