import { test, expect } from "@playwright/test";

test.describe("Targets and scans (requires seeded admin + live Docker backend)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("admin@secharden.local").fill(process.env.E2E_ADMIN_EMAIL || "admin@secharden.local");
    await page.getByPlaceholder("••••••••").fill(process.env.E2E_ADMIN_PASSWORD || "ChangeMe123!");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL("/");
  });

  test("can navigate to Targets and see the create form", async ({ page }) => {
    await page.getByRole("link", { name: /targets/i }).click();
    await expect(page).toHaveURL(/\/targets/);
    await page.getByRole("button", { name: /new target/i }).click();
    await expect(page.getByPlaceholder(/target name/i)).toBeVisible();
  });

  test("scan history page loads and filters by status", async ({ page }) => {
    await page.getByRole("link", { name: /^scans$/i }).click();
    await expect(page).toHaveURL(/\/scans/);
    await page.getByRole("button", { name: "completed" }).click();
    await expect(page.locator("table")).toBeVisible();
  });
});
