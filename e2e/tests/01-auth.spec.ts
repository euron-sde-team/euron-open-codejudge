import { expect, test } from "@playwright/test";

import { ADMIN, watchConsole } from "../helpers";

test.describe("sign in", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("signed-out visitors browse public problems without errors", async ({ page }) => {
    const errors = watchConsole(page);
    await page.goto("/problems");
    await expect(page.getByRole("heading", { name: "Problems" })).toBeVisible();
    await expect(page.getByRole("link", { name: /Sum of Two/ })).toBeVisible();
    await page.getByRole("link", { name: /Sum of Two/ }).click();
    await expect(page.getByText("Sign in to run your code and submit it for a verdict.")).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("a wrong password is explained; the right one signs you in", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#email").fill(ADMIN.email);
    await page.locator("#password").fill("not-the-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByText("Email or password is incorrect")).toBeVisible();
    await page.locator("#password").fill(ADMIN.password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  });

  test("protected pages send you to sign in, then back to where you were", async ({ page }) => {
    await page.goto("/submissions");
    await expect(page).toHaveURL(/\/login\?next=%2Fsubmissions/);
    await page.locator("#email").fill(ADMIN.email);
    await page.locator("#password").fill(ADMIN.password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page).toHaveURL(/\/submissions$/);
    await expect(page.getByRole("heading", { name: "Submissions" })).toBeVisible();
  });

  test("a crafted next= cannot send you to another site", async ({ page }) => {
    await page.goto("/login?next=/%5Cevil.example");
    await page.locator("#email").fill(ADMIN.email);
    await page.locator("#password").fill(ADMIN.password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    expect(new URL(page.url()).host).toBe(new URL(process.env.WEB_URL || "http://localhost:4710").host);
  });

  test("signing out ends the session for good", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#email").fill(ADMIN.email);
    await page.locator("#password").fill(ADMIN.password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
    const cookie = (await page.context().cookies()).find((c) => c.name === "cj_session");
    expect(cookie).toBeTruthy();
    await page.getByRole("button", { name: "Account menu" }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page.getByText("Signed out.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Account menu" })).toHaveCount(0);
    // Replaying the old cookie no longer works: the server refused that session for good.
    await page.context().addCookies([{ ...cookie!, expires: -1 }]);
    expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401);
  });
});
