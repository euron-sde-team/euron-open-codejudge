import { expect, test } from "@playwright/test";

import { ADMIN, RUN, SUM_OK, apiAs, localInput, newStudent, removeContest, removeProblem, sumProblem, typeCode, watchConsole } from "../helpers";

/**
 * AC7 in the browser: staff run an ICPC contest that starts now; a student registers,
 * solves a problem and appears on the scoreboard with the solve; a clarification asked by
 * the student is answered for everyone.
 */
test("a contest from creation to the scoreboard and a public clarification", async ({ page, browser }) => {
  const errors = watchConsole(page);
  const admin = await apiAs(ADMIN.email);
  const problem = await sumProblem(admin, `contest-sum-${RUN}`, "private");

  // Staff create the contest in the web app: ICPC, starting now, for two hours.
  await page.goto("/contests");
  await page.getByRole("button", { name: "New contest" }).click();
  await page.locator("#c-title").fill(`Evening Cup ${RUN}`);
  await page.locator("#c-slug").fill(`evening-cup-${RUN}`);
  await page.locator("#c-start").fill(localInput(-1));
  await page.locator("#c-end").fill(localInput(120));
  await page.getByRole("button", { name: "Create contest" }).click();
  await expect(page).toHaveURL(new RegExp(`/contests/evening-cup-${RUN}\\?tab=manage`));
  await page.locator("#cp-slug").fill(problem.slug);
  await page.getByRole("button", { name: "Add problem" }).click();
  await expect(page.getByText("Problem added.")).toBeVisible();

  // A student registers and solves problem A (a private problem, open through the contest).
  const student = await newStudent(browser, admin, "Kai Moreno");
  const s = student.page;
  await s.goto(`/contests/evening-cup-${RUN}`);
  await s.getByRole("button", { name: "Register" }).click();
  await expect(s.getByText("Registered. Good luck.")).toBeVisible();
  await s.goto(`/contests/evening-cup-${RUN}/problems/A`);
  await typeCode(s, SUM_OK);
  await s.getByRole("button", { name: "Submit" }).click();
  await expect(s.getByText("Accepted").first()).toBeVisible({ timeout: 90_000 });

  // The scoreboard shows the solve: one problem, a first-try "+" with its minute.
  await s.goto(`/contests/evening-cup-${RUN}?tab=scoreboard`);
  const row = s.getByRole("row", { name: /Kai Moreno/ });
  await expect(row).toBeVisible();
  await expect(row.getByRole("cell").nth(2)).toHaveText("1");
  await expect(row).toContainText("+");

  // A clarification, answered by staff for everyone.
  await s.goto(`/contests/evening-cup-${RUN}?tab=clarifications`);
  await s.getByRole("textbox", { name: "Your question" }).fill("Can a and b be negative?");
  await s.getByRole("button", { name: "Send question" }).click();
  await expect(s.getByText("Sent. The answer appears in this list.")).toBeVisible();

  await page.goto(`/contests/evening-cup-${RUN}?tab=clarifications`);
  await expect(page.getByText("Can a and b be negative?")).toBeVisible();
  await page.getByRole("textbox", { name: "Your answer" }).first().fill("Yes, both can be negative.");
  await page.getByRole("switch", { name: "Answer for everyone" }).first().click();
  await page.getByRole("button", { name: "Send answer" }).first().click();
  await s.reload();
  await expect(s.getByText("Yes, both can be negative.")).toBeVisible();

  expect(errors.filter((e) => /Content Security Policy|Refused to/i.test(e))).toEqual([]);
  await student.context.close();
  await removeContest(admin, `evening-cup-${RUN}`);
  await removeProblem(admin, problem.id);
  await admin.dispose();
});
