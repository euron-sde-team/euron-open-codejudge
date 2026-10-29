import { expect, test } from "@playwright/test";

import { PASSWORD, RUN, watchConsole } from "../helpers";

/** Admin screens: settings take effect for visitors, and users are added and listed. */
test("turning sign-up off closes it for visitors, and turning it on reopens it", async ({ page, browser }) => {
  const errors = watchConsole(page);
  const toggle = page.getByRole("switch", { name: "Anyone can create an account" });
  const setSignup = async (on: boolean) => {
    await page.goto("/admin/settings");
    if ((await toggle.getAttribute("aria-checked")) !== String(on)) await toggle.click();
    await page.getByRole("button", { name: "Save settings" }).first().click();
    await expect(page.getByText(/saved/i).first()).toBeVisible();
  };
  const visitor = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const v = await visitor.newPage();
  try {
    await setSignup(false);
    expect((await (await v.request.get("/api/v1/org/public")).json()).allow_signup).toBe(false);
    await v.goto("/signup");
    await expect(v.getByRole("button", { name: "Create account" })).toBeDisabled();
  } finally {
    await setSignup(true);
  }
  expect((await (await v.request.get("/api/v1/org/public")).json()).allow_signup).toBe(true);
  await v.goto("/signup");
  await expect(v.getByRole("button", { name: "Create account" })).toBeEnabled();
  await visitor.close();
  expect(errors).toEqual([]);
});

test("an admin adds a user who then appears in the list", async ({ page }) => {
  const errors = watchConsole(page);
  const email = `drew.patel.${RUN}@example.test`;
  await page.goto("/admin/users");
  await page.getByRole("button", { name: "Add user" }).click();
  await page.locator("#u-name").fill("Drew Patel");
  await page.locator("#u-email").fill(email);
  await page.locator("#u-pw").fill(PASSWORD);
  await page.getByRole("dialog").getByRole("button", { name: "Add user" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText(email)).toBeVisible();
  expect(errors).toEqual([]);
});
