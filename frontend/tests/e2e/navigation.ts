import { expect, type Page } from "@playwright/test";

export async function openSection(page: Page, section: string) {
  if (new URL(page.url()).hash === `#${section}`) return;
  const nav = page.locator("#workspace-navigation");
  await nav.waitFor({ state: "attached" });
  const link = nav.locator(`a[href="#${section}"]`);
  if (!(await nav.isVisible())) await page.locator('button[aria-controls="workspace-navigation"]').click();
  await link.click();
  await expect(link).toHaveAttribute("aria-current", "page");
}
