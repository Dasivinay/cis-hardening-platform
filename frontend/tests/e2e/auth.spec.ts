import { test, expect } from "@playwright/test";

/**
 * These E2E tests assume the full stack is running (docker compose up) with
 * the default seeded admin account. Run with: npx playwright test
 */

test.describe("Authentication", () => {
  test("redirects unauthenticated users to /login", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows an error on invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("admin@secharden.local").fill("nobody@nowhere.local");
    await page.getByPlaceholder("••••••••").fill("wrong-password");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByText(/invalid email or password/i)).toBeVisible();
  });

  test("logs in with seeded admin and reaches the dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("admin@secharden.local").fill(process.env.E2E_ADMIN_EMAIL || "admin@secharden.local");
    await page.getByPlaceholder("••••••••").fill(process.env.E2E_ADMIN_PASSWORD || "ChangeMe123!");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL("/");
    await expect(page.getByText("Overview")).toBeVisible();
  });
});
