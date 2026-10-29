import { expect, test } from "@playwright/test";

import { watchConsole } from "../helpers";

/** The staff views over the seeded month: plagiarism results and the analytics overview. */
test("a plagiarism check lists flagged pairs and shows both sides", async ({ page }) => {
  const errors = watchConsole(page);
  await page.goto("/plagiarism");
  await expect(page.getByRole("heading", { name: "Plagiarism" })).toBeVisible();
  await page.getByRole("row").nth(1).getByRole("link").first().click();
  await expect(page).toHaveURL(/\/plagiarism\/runs\//);
  const pairs = page.getByRole("link", { name: / and / });
  await expect(pairs.first()).toBeVisible();
  await pairs.first().click();
  await expect(page).toHaveURL(/\/plagiarism\/pairs\//);
  await expect(page.getByText(/similar/).first()).toBeVisible();
  await expect(page.getByText(/talk to the people before drawing a conclusion/)).toBeVisible();
  expect(errors).toEqual([]);
});

test("the analytics overview shows the month with real numbers", async ({ page }) => {
  const errors = watchConsole(page);
  await page.goto("/analytics");
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  await expect(page.getByText("Submissions per day")).toBeVisible();
  // The daily chart draws bars, and the totals are not empty.
  await expect(page.locator(".recharts-rectangle").first()).toBeVisible();
  await expect(page.getByText("Most attempted problems")).toBeVisible();
  await expect(page.getByText("Python 3").first()).toBeVisible();
  expect(errors).toEqual([]);
});
