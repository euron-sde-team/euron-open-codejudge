import { expect, test } from "@playwright/test";

import { ADMIN, INTERVIEWER, RUN, SUM_OK, apiAs, inviteLink, removeProblem, signedInContext, sumProblem, typeCode, watchConsole } from "../helpers";

/**
 * AC9 in the browser: an interviewer creates an assessment and invites a candidate by
 * email; the candidate (no account) opens the one-time link from the email, reads the
 * preview without starting the clock, starts, solves, and finishes; the interviewer's
 * report has the score, the code and the timeline.
 */
test("an interview: invite by email, take it from the link, read the report", async ({ browser }) => {
  const admin = await apiAs(ADMIN.email);
  const problem = await sumProblem(admin, `screen-sum-${RUN}`, "private");
  const interviewer = await signedInContext(browser, INTERVIEWER);
  const i = interviewer.page;
  const errors = watchConsole(i);

  // The interviewer creates the assessment and invites a candidate.
  await i.goto("/assessments");
  await i.getByRole("button", { name: "New assessment" }).first().click();
  await i.locator("#as-title").fill(`Platform Engineer ${RUN}`);
  await i.getByRole("textbox", { name: "Problem 1 slug" }).fill(problem.slug);
  await i.locator("#as-inst").fill("Solve the problem. Explain your approach in a comment.");
  await i.getByRole("button", { name: "Create assessment" }).click();
  await expect(i.getByRole("heading", { name: `Platform Engineer ${RUN}` })).toBeVisible();
  const email = `jamie.cho.${RUN}@example.com`;
  await i.getByRole("textbox", { name: "Candidates, one per line" }).fill(`Jamie Cho <${email}>`);
  await i.getByRole("button", { name: "Send invitations" }).click();
  await expect(i.getByText(email)).toBeVisible();

  // The candidate opens the emailed link in a fresh browser (no account, no session).
  const link = await inviteLink(email);
  const candidate = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const c = await candidate.newPage();
  const candidateErrors = watchConsole(c);
  await c.goto(link);
  // The preview: title, duration and instructions, before any clock starts.
  await expect(c.getByRole("heading", { name: `Platform Engineer ${RUN}` })).toBeVisible();
  await expect(c.getByText("Solve the problem. Explain your approach in a comment.")).toBeVisible();
  await expect(c.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  await c.getByRole("button", { name: "Start the assessment" }).click();
  await expect(c.getByText(/Time left/)).toBeVisible();

  await typeCode(c, SUM_OK);
  await c.getByRole("button", { name: "Submit" }).click();
  await expect(c.getByText("Accepted").first()).toBeVisible({ timeout: 90_000 });
  await c.getByRole("button", { name: "Finish" }).click();
  await c.getByRole("button", { name: "Finish now" }).click();
  await expect(c.getByText("Submitted. Thank you.")).toBeVisible();

  // The interviewer's report: the score, the code and the timeline.
  await i.reload();
  await i.getByRole("row", { name: new RegExp(email.replace(/\./g, "\\.")) }).getByRole("link", { name: "Report" }).click();
  await expect(i.getByRole("heading", { name: "Jamie Cho" })).toBeVisible();
  await expect(i.getByText("100 / 100").first()).toBeVisible();
  await expect(i.getByText("Started the assessment")).toBeVisible();
  await expect(i.getByText("Finished the assessment")).toBeVisible();
  await expect(i.getByText(/not proof/)).toBeVisible();

  for (const list of [errors, candidateErrors]) {
    expect(list.filter((e) => /Content Security Policy|Refused to/i.test(e))).toEqual([]);
  }
  await candidate.close();
  const assessmentId = i.url().split("/assessments/")[1].split("/")[0];
  await interviewer.context.close();
  await admin.delete(`/api/v1/assessments/${assessmentId}`);
  await removeProblem(admin, problem.id);
  await admin.dispose();
});
