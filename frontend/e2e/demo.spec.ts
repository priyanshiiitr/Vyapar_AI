import { test, expect } from "@playwright/test";

test("overview loads and can seed demo data", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Vyapar AI")).toBeVisible();
  await page.getByRole("button", { name: /Load demo data/i }).click();
  await expect(page.getByText(/33,000/)).toBeVisible({ timeout: 15000 });
});
