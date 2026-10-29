import { type APIRequestContext, type Browser, type BrowserContext, expect, type Page, request } from "@playwright/test";

const BASE = process.env.WEB_URL || "http://localhost:4710";
const MAILPIT = process.env.MAILPIT_URL || "http://localhost:4725";
export const PASSWORD = process.env.E2E_PASSWORD || process.env.CJ_DEMO_PASSWORD || "";
export const ADMIN = { email: process.env.E2E_EMAIL || "admin@codejudge.local", password: PASSWORD };
export const TEACHER = "priya.raman@codejudge.local";
export const INTERVIEWER = "daniel.okafor@codejudge.local";

/** Mutations through the API carry the CSRF header the web app sends. */
export const CSRF = { "x-codejudge-csrf": "1" };

/** A per-run suffix so suites can run repeatedly against the same demo database. */
export const RUN = process.env.E2E_RUN || Date.now().toString(36).slice(-5);

/** A solution and a wrong one for the "add two numbers" problems the suites create. */
export const SUM_OK = "a, b = map(int, input().split())\nprint(a + b)\n";
export const SUM_WRONG = "a, b = map(int, input().split())\nprint(a - b)\n";
export const SUM_TESTS = [
  { name: "sample/1", input: "1 2\n", answer: "3\n" },
  { name: "secret/1", input: "40 2\n", answer: "42\n" },
  { name: "secret/2", input: "-5 5\n", answer: "0\n" },
];

/** Fail the test on any console error or CSP violation the page reports. */
export function watchConsole(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

async function retrying(fn: () => Promise<import("@playwright/test").APIResponse>) {
  for (let i = 0; i < 10; i++) {
    const resp = await fn();
    if (resp.status() !== 429) return resp;
    await new Promise((r) => setTimeout(r, Number(resp.headers()["retry-after"] ?? "5") * 1000));
  }
  return fn();
}

/** An API client signed in as someone (waits out the sign-in limit if needed). */
export async function apiAs(email: string, password = PASSWORD): Promise<APIRequestContext> {
  const ctx = await request.newContext({ baseURL: BASE, extraHTTPHeaders: CSRF });
  const resp = await retrying(() => ctx.post("/api/v1/auth/login", { data: { email, password } }));
  expect(resp.status(), await resp.text()).toBe(200);
  return ctx;
}

/** JSON from the API, asserting success. */
export async function call<T = unknown>(ctx: APIRequestContext, method: string, path: string, data?: unknown): Promise<T> {
  const resp = await retrying(() => ctx.fetch(path, { method, data }));
  expect(resp.status(), `${method} ${path}: ${await resp.text()}`).toBeLessThan(300);
  return (resp.status() === 204 ? null : await resp.json()) as T;
}

/** A new student account, and a browser context signed in as them. */
export async function newStudent(browser: Browser, admin: APIRequestContext, name: string): Promise<{ email: string; context: BrowserContext; page: Page }> {
  const email = `${name.toLowerCase().replace(/\W+/g, ".")}.${RUN}.${Math.random().toString(36).slice(2, 6)}@example.test`;
  await call(admin, "POST", "/api/v1/users", { email, name, role: "student", password: PASSWORD });
  return { email, ...(await signedInContext(browser, email)) };
}

/** A browser context carrying the session of an existing account. */
export async function signedInContext(browser: Browser, email: string): Promise<{ context: BrowserContext; page: Page }> {
  const api = await apiAs(email);
  const state = await api.storageState();
  await api.dispose();
  const context = await browser.newContext({ storageState: state });
  return { context, page: await context.newPage() };
}

/** A published "add two numbers" problem, made through the API (setup for other journeys). */
export async function sumProblem(admin: APIRequestContext, slug: string, visibility: "public" | "private" = "public"): Promise<{ id: string; slug: string }> {
  const p = await call<{ id: string; slug: string }>(admin, "POST", "/api/v1/problems", {
    slug,
    title: `Sum ${slug.slice(-5)}`,
    statement_md: "Read $a$ and $b$, print $a + b$.",
    visibility,
  });
  await call(admin, "POST", `/api/v1/problems/${p.id}/versions`, { tests: SUM_TESTS });
  await call(admin, "POST", `/api/v1/problems/${p.id}/references`, { name: "ok", language: "python3", source: SUM_OK });
  await call(admin, "POST", `/api/v1/problems/${p.id}/references/judge`);
  await expect
    .poll(async () => (await call<{ publishable: boolean }>(admin, "GET", `/api/v1/problems/${p.id}/admin`)).publishable, { timeout: 120_000 })
    .toBe(true);
  await call(admin, "POST", `/api/v1/problems/${p.id}/publish`);
  return p;
}

/** Replace the code in a Monaco editor: focus its input, select all, then insert as-is
 * (insertText bypasses auto-indent and auto-closing brackets). */
export async function typeCode(page: Page, code: string, editor = page.locator(".monaco-editor").first()): Promise<void> {
  await editor.click({ position: { x: 120, y: 20 } });
  const input = editor.locator("textarea").first();
  await input.focus();
  // Select all with whichever modifier Monaco binds on this platform, then delete.
  for (const combo of ["Meta+KeyA", "Control+KeyA"]) {
    await page.keyboard.press(combo);
    await page.keyboard.press("Backspace");
    if (!(await editor.locator(".view-lines").innerText()).trim()) break;
  }
  await expect(editor.locator(".view-lines")).toHaveText(/^\s*$/);
  await page.keyboard.insertText(code);
}

/** Pick an option in one of the web app's custom selects. */
export async function choose(page: Page, triggerId: string, option: string | RegExp): Promise<void> {
  await page.locator(`#${triggerId}`).click();
  await page.getByRole("option", { name: option }).first().click();
}

/** The one-time /take/ link from the newest invitation email to an address. */
export async function inviteLink(email: string): Promise<string> {
  for (let i = 0; i < 40; i++) {
    const found = (await (await fetch(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`)).json()) as { messages?: { ID: string }[] };
    if (found.messages?.length) {
      const msg = (await (await fetch(`${MAILPIT}/api/v1/message/${found.messages[0].ID}`)).json()) as { Text: string; HTML: string };
      const m = /\/take\/([A-Za-z0-9_-]+)/.exec(`${msg.Text} ${msg.HTML}`);
      if (m) return `/take/${m[1]}`;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`no invitation email reached Mailpit for ${email}`);
}

/** A datetime-local value for a moment relative to now, in the browser's time zone. */
export function localInput(offsetMinutes: number): string {
  const d = new Date(Date.now() + offsetMinutes * 60_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Remove what a suite created, so reruns leave the demo data as it was. */
export async function removeProblem(admin: APIRequestContext, ref: string): Promise<void> {
  const resp = await admin.get(`/api/v1/problems/${ref}`);
  if (resp.ok()) await admin.delete(`/api/v1/problems/${((await resp.json()) as { id: string }).id}`);
}

export async function removeContest(admin: APIRequestContext, slug: string): Promise<void> {
  const resp = await admin.get(`/api/v1/contests/${slug}`);
  if (resp.ok()) await admin.delete(`/api/v1/contests/${((await resp.json()) as { id: string }).id}`);
}
