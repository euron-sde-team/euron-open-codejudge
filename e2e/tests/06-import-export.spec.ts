import { expect, test } from "@playwright/test";

import { ADMIN, RUN, apiAs, call, removeProblem, sumProblem, watchConsole } from "../helpers";

/**
 * AC6 in the browser: a problem exports as a Kattis package (a zip with problem.yaml and
 * data/), and that zip imports back as a new problem with the same tests.
 */
test("export a problem as a package and import it as a new one", async ({ page }) => {
  const errors = watchConsole(page);
  const admin = await apiAs(ADMIN.email);
  const original = await sumProblem(admin, `export-sum-${RUN}`, "private");

  await page.goto(`/manage/problems/${original.id}`);
  await page.getByRole("button", { name: "More actions" }).click();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("menuitem", { name: "Export package" }).click()]);
  expect(download.suggestedFilename()).toBe(`${original.slug}.zip`);
  const zipPath = (await download.path())!;

  await page.goto("/manage/problems");
  await page.getByRole("button", { name: "Import package" }).click();
  await page.locator("#pkg-file").setInputFiles(zipPath);
  await page.locator("#pkg-slug").fill(`imported-sum-${RUN}`);
  await page.getByRole("button", { name: "Import", exact: true }).click();
  // The result first (tests, groups, solutions, any warnings), then on to the editor.
  await expect(page.getByText(/Imported .*3 tests/)).toBeVisible();
  await page.getByRole("button", { name: "Open in the editor" }).click();
  await expect(page).toHaveURL(/\/manage\/problems\/[0-9a-f-]{36}/);
  await expect(page.getByText("Draft", { exact: true })).toBeVisible();

  // Same tests, byte for byte: the packages have the same hash.
  const copyId = page.url().split("/manage/problems/")[1].split("?")[0];
  type Admin = { versions: { package_sha256: string; tests: unknown[] }[]; references: unknown[] };
  const a = await call<Admin>(admin, "GET", `/api/v1/problems/${original.id}/admin`);
  const b = await call<Admin>(admin, "GET", `/api/v1/problems/${copyId}/admin`);
  expect(b.versions[0].package_sha256).toBe(a.versions[0].package_sha256);
  expect(b.references.length).toBe(1);

  expect(errors.filter((e) => /Content Security Policy|Refused to/i.test(e))).toEqual([]);
  await removeProblem(admin, copyId);
  await removeProblem(admin, original.id);
  await admin.dispose();
});
