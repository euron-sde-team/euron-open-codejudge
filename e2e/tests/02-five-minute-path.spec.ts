import { expect, test } from "@playwright/test";

import { ADMIN, RUN, SUM_OK, SUM_WRONG, apiAs, newStudent, removeProblem, typeCode, watchConsole } from "../helpers";

/**
 * AC13, the promise of the project: a problem written in the browser, with tests and a
 * reference solution the real judge must accept before it can be published, then solved
 * by a student who gets a live verdict from the sandbox. A wrong answer explains itself on
 * the sample and shows nothing of the hidden tests.
 */
test("staff write and publish a problem; a student solves it with a live verdict", async ({ page, browser }) => {
  const errors = watchConsole(page);
  const slug = `add-two-${RUN}`;

  // Staff: create the problem.
  await page.goto("/manage/problems");
  await page.getByRole("button", { name: "New problem" }).click();
  await page.locator("#p-title").fill(`Add Two ${RUN}`);
  await page.locator("#p-slug").fill(slug);
  await page.getByRole("button", { name: "Create draft" }).click();
  await expect(page).toHaveURL(/\/manage\/problems\/[0-9a-f-]{36}/);
  await expect(page.getByText("Draft", { exact: true })).toBeVisible();

  // Tests: one sample, two hidden tests.
  await page.getByRole("tab", { name: "Tests" }).click();
  await page.getByRole("button", { name: "Write tests" }).click();
  await page.getByRole("button", { name: "Hidden test" }).click();
  const tests = [
    ["1 2\n", "3\n"],
    ["40 2\n", "42\n"],
    ["-5 5\n", "0\n"],
  ];
  for (const [i, [input, answer]] of tests.entries()) {
    await page.getByRole("textbox", { name: `Test ${i + 1} input` }).fill(input);
    await page.getByRole("textbox", { name: `Test ${i + 1} expected answer` }).fill(answer);
  }
  await page.getByRole("button", { name: "Save tests" }).click();
  await expect(page.getByText(/Current tests \(version 1\)/)).toBeVisible();

  // A reference solution, judged by the real judge.
  await page.getByRole("tab", { name: "Reference solutions" }).click();
  await page.getByRole("button", { name: "Add solution" }).click();
  await page.locator("#ref-name").fill("straightforward");
  await typeCode(page, SUM_OK);
  await page.getByRole("button", { name: "Add solution" }).last().click();
  await page.getByRole("button", { name: "Judge all" }).click();
  await expect(page.getByLabel("Gets its expected verdict")).toBeVisible({ timeout: 120_000 });

  // Publish (refused until the reference solution was accepted).
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByText("Published", { exact: true })).toBeVisible();

  // A student solves it.
  const admin = await apiAs(ADMIN.email);
  const student = await newStudent(browser, admin, "Robin Ito");
  const s = student.page;
  const studentErrors = watchConsole(s);
  await s.goto(`/problems/${slug}`);
  await expect(s.getByRole("heading", { name: `Add Two ${RUN}` })).toBeVisible();
  await expect(s.getByRole("combobox", { name: "Language" })).toContainText("Python 3");
  await typeCode(s, SUM_OK);

  await s.getByRole("button", { name: "Run samples" }).click();
  await expect(s.locator("[data-verdict='AC']").first()).toBeVisible({ timeout: 90_000 });

  await s.getByRole("button", { name: "Submit" }).click();
  await expect(s.getByText("Accepted").first()).toBeVisible({ timeout: 90_000 });
  await expect(s.getByText("100 / 100").first()).toBeVisible();

  // A wrong answer: the sample shows what went wrong; hidden tests show no data.
  await typeCode(s, SUM_WRONG);
  await s.getByRole("button", { name: "Submit" }).click();
  await expect(s.getByText("Wrong answer").first()).toBeVisible({ timeout: 90_000 });
  const submission = await (await s.request.get("/api/v1/submissions?mine=true&limit=1")).json();
  const latest = await (await s.request.get(`/api/v1/submissions/${submission.items[0].id}`)).json();
  expect(latest.verdict).toBe("WA");
  const hidden = latest.tests.filter((t: { name: string }) => t.name.startsWith("secret/"));
  expect(hidden.length).toBeGreaterThan(0);
  for (const t of hidden) {
    expect(t.output).toBeNull();
    expect(t.message).toBeNull();
  }
  expect(JSON.stringify(latest)).not.toContain("40 2");

  expect(errors.filter((e) => /Content Security Policy|Refused to/i.test(e))).toEqual([]);
  expect(studentErrors.filter((e) => /Content Security Policy|Refused to/i.test(e))).toEqual([]);
  await student.context.close();
  await removeProblem(admin, slug);
  await admin.dispose();
});
