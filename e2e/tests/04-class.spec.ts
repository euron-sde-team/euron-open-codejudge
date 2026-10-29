import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { ADMIN, RUN, SUM_OK, TEACHER, apiAs, call, newStudent, removeProblem, signedInContext, sumProblem, typeCode, watchConsole } from "../helpers";

/**
 * AC8 in the browser: a teacher creates a class and an assignment; a student joins with
 * the class code, solves the assignment's problem, and the teacher's gradebook shows the
 * mark and downloads as CSV.
 */
test("a class: create, join with the code, submit, see the mark in the gradebook", async ({ browser }) => {
  const admin = await apiAs(ADMIN.email);
  const problem = await sumProblem(admin, `class-sum-${RUN}`, "private");
  const teacher = await signedInContext(browser, TEACHER);
  const t = teacher.page;
  const errors = watchConsole(t);

  // The teacher creates the class and an assignment that is open now.
  await t.goto("/classes");
  await t.getByRole("button", { name: "New class" }).first().click();
  await t.locator("#class-name").fill(`Algorithms ${RUN}`);
  await t.getByRole("button", { name: "Create class" }).click();
  await expect(t.getByRole("heading", { name: `Algorithms ${RUN}` })).toBeVisible();
  const classId = t.url().split("/classes/")[1].split("?")[0];
  // A new class opens on its roster (the next thing a teacher usually does).
  await t.getByRole("tab", { name: "Assignments" }).click();
  await t.getByRole("button", { name: "New assignment" }).first().click();
  await t.locator("#a-title").fill(`Warm-up ${RUN}`);
  await t.getByRole("textbox", { name: "Problem 1 slug" }).fill(problem.slug);
  await t.getByRole("button", { name: "Create assignment" }).click();
  await expect(t.getByText(`Warm-up ${RUN}`)).toBeVisible();

  // The student joins with the class code and solves the problem.
  const { join_code: code } = await call<{ join_code: string }>(admin, "GET", `/api/v1/classes/${classId}`);
  const student = await newStudent(browser, admin, "Noor Hassan");
  const s = student.page;
  await s.goto("/classes");
  await s.getByRole("button", { name: "Join a class" }).first().click();
  await s.locator("#class-code").fill(code);
  await s.getByRole("button", { name: "Join", exact: true }).click();
  await expect(s.getByText(`Algorithms ${RUN}`).first()).toBeVisible();
  await s.getByText(`Algorithms ${RUN}`).first().click();
  await s.getByText(`Warm-up ${RUN}`).click();
  await s.getByText(`Sum ${problem.slug.slice(-5)}`).click();
  await typeCode(s, SUM_OK);
  await s.getByRole("button", { name: "Submit" }).click();
  await expect(s.getByText("Accepted").first()).toBeVisible({ timeout: 90_000 });

  // The teacher's gradebook shows the full mark, and the CSV downloads with it.
  await t.goto(`/classes/${classId}`);
  await t.getByText(`Warm-up ${RUN}`).click();
  await t.getByRole("tab", { name: "Gradebook" }).click();
  const row = t.getByRole("row", { name: /Noor Hassan/ });
  await expect(row).toContainText("100 / 100");
  const [download] = await Promise.all([t.waitForEvent("download"), t.getByRole("button", { name: "Download CSV" }).click()]);
  const csv = await readFile((await download.path())!, "utf8");
  expect(csv).toContain("Noor Hassan");
  expect(csv.split("\n")[0]).toMatch(/^name,email,.*total \(100\)/);

  expect(errors.filter((e) => /Content Security Policy|Refused to/i.test(e))).toEqual([]);
  await student.context.close();
  await teacher.context.close();
  await admin.delete(`/api/v1/classes/${classId}`);
  await removeProblem(admin, problem.id);
  await admin.dispose();
});
