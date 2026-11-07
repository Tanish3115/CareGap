import { test, expect } from "@playwright/test";

test("only the six requested languages are selectable and persist across reloads", async ({ page }, testInfo) => {
  await page.goto("/");
  const selector = page.getByLabel("Application language / भाषा", { exact: true });
  expect(await selector.locator("option").evaluateAll(options => options.map(option => (option as HTMLOptionElement).value).sort())).toEqual(["en", "hi", "kn", "ml", "ta", "te"]);
  for (const [code, signIn] of [["kn", "ಲಾಗಿನ್ ಮಾಡಿ"], ["te", "సైన్ ఇన్"], ["ta", "உள்நுழைக"], ["ml", "സൈൻ ഇൻ"], ["hi", "साइन इन"], ["en", "Sign In"]]) {
    await selector.selectOption(code);
    await expect(page.locator("html")).toHaveAttribute("lang", code);
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await expect(page.getByRole("link", { name: signIn, exact: true })).toBeVisible();
    await page.reload();
    await expect(selector).toHaveValue(code);
    await expect(page.getByRole("link", { name: signIn, exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (code === "kn") await page.screenshot({ path: testInfo.outputPath("kannada-mobile.png"), fullPage: true });
  }
  // Unknown or retired saved locales must not crash the application.
  await page.evaluate(() => localStorage.setItem("caregap-language", "bn"));
  await page.reload();
  await expect(selector).toHaveValue("en");
});
