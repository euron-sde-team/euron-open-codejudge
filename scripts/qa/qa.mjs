/**
 * Browser QA (make qa): signs in through the real form as each role, visits every page in
 * light and dark at desktop and phone width, saves screenshots, and fails on console
 * errors, failed or 4xx/5xx requests, broken images, error states, empty pages with no
 * explanation, and horizontal overflow.
 *
 *   make qa
 *   QA_BASE=http://localhost:4710 QA_OUT=./output node qa.mjs
 *   QA_PAGES=/problems,/contests QA_THEMES=dark QA_SIZES=desktop node qa.mjs
 *
 * Needs the seeded stack (make up && make demo). Uses Puppeteer's bundled Chromium; set
 * CHROME_PATH to use a local browser instead.
 */
import { mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer";

const BASE = process.env.QA_BASE ?? "http://localhost:4710";
const MAILPIT = process.env.QA_MAILPIT ?? "http://localhost:4725";
const OUT = process.env.QA_OUT ?? path.resolve("output");
const PASSWORD = process.env.QA_PASSWORD ?? process.env.CJ_DEMO_PASSWORD ?? "";
const CHROME = process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH) ? process.env.CHROME_PATH : undefined;

const ADMIN = "admin@codejudge.local";
const STUDENT = "aarav.mehta@students.example";

// Pages per role. Placeholders are resolved from the seeded data once.
const ROLE_PAGES = {
  anonymous: ["/login", "/signup", "/problems", "/problems/:problem"],
  admin: [
    "/problems",
    "/problems/:problem",
    "/submissions",
    "/submissions/:submission",
    "/contests",
    "/contests/:contest",
    "/contests/:contest/problems/A",
    "/contests/:contest?tab=scoreboard",
    "/contests/:contest?tab=clarifications",
    "/contests/autumn-sprint-2026?tab=scoreboard",
    "/classes",
    "/classes/:class",
    "/classes/:class?tab=roster",
    "/assignments/:assignment",
    "/assignments/:assignment?tab=gradebook",
    "/assessments",
    "/assessments/:assessment",
    "/assessments/:assessment/invitations/:invitation",
    "/manage/problems",
    "/manage/problems/:problemId",
    "/manage/problems/:problemId?tab=tests",
    "/manage/problems/:problemId?tab=solutions",
    "/plagiarism",
    "/plagiarism/runs/:run",
    "/plagiarism/pairs/:pair",
    "/analytics",
    "/analytics/problems/:problem",
    "/admin/users",
    "/admin/settings",
    "/admin/system",
    "/admin/audit",
  ],
  student: [
    "/problems",
    "/problems/:problem",
    "/submissions",
    "/contests",
    "/contests/:contest",
    "/contests/autumn-sprint-2026?tab=scoreboard",
    "/classes",
    "/classes/:class",
    "/assignments/:assignment",
    "/assignments/:assignment/problems/:assignmentProblem",
    "/progress",
  ],
  candidate: ["/take"],
};
const ONLY = process.env.QA_PAGES ? new Set(process.env.QA_PAGES.split(",")) : null;
const ROLES = (process.env.QA_ROLES ?? "anonymous,admin,student,candidate").split(",");
const THEMES = (process.env.QA_THEMES ?? "light,dark").split(",");
const SIZES = {
  desktop: { width: 1440, height: 900 },
  phone: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};
const SIZE_KEYS = (process.env.QA_SIZES ?? "desktop,phone").split(",");
const FULL = process.env.QA_FULL !== "0";

function slug(p) {
  return p.replace(/^\//, "").replace(/[/:?=]/g, "-") || "home";
}

async function api(token, method, url, body) {
  const resp = await fetch(`${BASE}${url}`, {
    method,
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json", "x-codejudge-csrf": "1" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) throw new Error(`${method} ${url}: ${resp.status} ${await resp.text()}`);
  return resp.status === 204 ? null : resp.json();
}

async function token(email) {
  const resp = await fetch(`${BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-codejudge-csrf": "1" },
    body: JSON.stringify({ email, password: PASSWORD }),
  });
  if (!resp.ok) throw new Error(`sign-in for ${email} failed (${resp.status}): run make demo first`);
  return (await resp.json()).session_token;
}

/** Ids of seeded records for the parameterised pages. */
async function resolveIds() {
  const t = await token(ADMIN);
  const subs = await api(t, "GET", "/api/v1/submissions?limit=20&verdict=WA");
  const problems = await api(t, "GET", "/api/v1/problems?q=sum-of-two");
  const classes = await api(t, "GET", "/api/v1/classes");
  const klass = classes.find((c) => c.name.startsWith("CS201")) ?? classes[0];
  const assignments = await api(t, "GET", `/api/v1/classes/${klass.id}/assignments`);
  const assignment = assignments.find((a) => a.title.startsWith("Week 4")) ?? assignments[0];
  const assessments = await api(t, "GET", "/api/v1/assessments");
  const assessment = assessments.find((a) => a.title.startsWith("Backend")) ?? assessments[0];
  const invitations = await api(t, "GET", `/api/v1/assessments/${assessment.id}/invitations`);
  const invitation = invitations.find((i) => i.status === "submitted") ?? invitations[0];
  const runs = await api(t, "GET", "/api/v1/plagiarism/runs");
  const run = await api(t, "GET", `/api/v1/plagiarism/runs/${runs[0].id}`);
  return {
    problem: "sum-of-two",
    problemId: problems.items[0].id,
    submission: subs.items[0].id,
    contest: "weekly-round-42",
    class: klass.id,
    assignment: assignment.id,
    assignmentProblem: "grid-escape",
    assessment: assessment.id,
    invitation: invitation.id,
    run: run.id,
    pair: run.pairs[0]?.id ?? "none",
    assessmentForCandidate: assessment.id,
  };
}

let candidateEmail = null;

/** Withdraw the QA candidate's invitation so reruns do not leave candidates in progress. */
async function revokeCandidate(ids) {
  if (!candidateEmail) return;
  const t = await token("daniel.okafor@codejudge.local");
  const list = await api(t, "GET", `/api/v1/assessments/${ids.assessmentForCandidate}/invitations`);
  const inv = list.find((i) => i.email === candidateEmail);
  if (inv && inv.status !== "revoked") {
    await api(t, "POST", `/api/v1/assessments/${ids.assessmentForCandidate}/invitations/${inv.id}/revoke`);
  }
}

/** A fresh candidate link (the seeded ones are used): invite, then read Mailpit. */
async function candidateToken(ids) {
  const t = await token("daniel.okafor@codejudge.local");
  const email = `qa-${Date.now().toString(36)}@example.com`;
  await api(t, "POST", `/api/v1/assessments/${ids.assessmentForCandidate}/invitations`, {
    candidates: [{ email, name: "Riley Quinn" }],
  });
  candidateEmail = email;
  for (let i = 0; i < 30; i++) {
    const found = await (await fetch(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`)).json();
    if (found.messages?.length) {
      const msg = await (await fetch(`${MAILPIT}/api/v1/message/${found.messages[0].ID}`)).json();
      const m = /\/take\/([A-Za-z0-9_-]+)/.exec(`${msg.Text} ${msg.HTML}`);
      if (m) return m[1];
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("the invitation email never reached Mailpit");
}

async function signInForm(page, email) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
  await page.type("#email", email);
  await page.type("#password", PASSWORD);
  await Promise.all([page.waitForNavigation({ waitUntil: "networkidle2" }), page.click("button[type=submit]")]);
}

function watch(page, sink) {
  page.on("console", (m) => {
    if (m.type() === "error") sink.push(m.text());
  });
  page.on("pageerror", (e) => sink.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => {
    const err = r.failure()?.errorText ?? "";
    if (!err.includes("ERR_ABORTED")) sink.push(`requestfailed ${r.url()} ${err}`);
  });
  page.on("response", (r) => {
    if (r.status() >= 400) sink.push(`HTTP ${r.status()} ${r.url()}`);
  });
}

async function inspect(page) {
  return page.evaluate(() => {
    const overflow = document.documentElement.scrollWidth - window.innerWidth;
    const broken = [...document.images].filter((img) => img.complete && img.naturalWidth === 0).map((img) => img.src);
    const errorStates = [...document.querySelectorAll("[data-qa='error-state']")].map((el) => el.textContent?.slice(0, 80) ?? "");
    const main = document.querySelector("main") ?? document.body;
    const text = (main.textContent ?? "").replace(/\s+/g, " ").trim();
    return { overflow, broken, errorStates, empty: text.length < 40 };
  });
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const ids = await resolveIds();
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-sandbox"] });
  const problems = [];
  let candidate = null;
  let visited = 0;

  for (const role of ROLES) {
    const pages = ROLE_PAGES[role].filter((p) => !ONLY || ONLY.has(p));
    if (!pages.length) continue;
    if (role === "candidate" && !candidate) candidate = await candidateToken(ids);
    for (const theme of THEMES) {
      for (const sizeKey of SIZE_KEYS) {
        const ctx = await browser.createBrowserContext();
        const page = await ctx.newPage();
        await page.setViewport(SIZES[sizeKey]);
        await page.evaluateOnNewDocument((t) => {
          try {
            localStorage.setItem("theme", t);
          } catch {}
        }, theme);
        const errors = [];
        watch(page, errors);
        if (role === "admin") await signInForm(page, ADMIN);
        if (role === "student") await signInForm(page, STUDENT);
        if (role === "candidate") {
          // The link stores the token and opens the assessment; starting it is part of the page.
          await page.goto(`${BASE}/take/${candidate}`, { waitUntil: "networkidle2" });
        }
        for (const p of pages) {
          const url = p.replace(/:(\w+)/g, (_, k) => ids[k] ?? k);
          errors.length = 0;
          await page.goto(`${BASE}${url}`, { waitUntil: "networkidle2", timeout: 60_000 });
          if (role === "candidate") {
            const start = await page.$("[data-qa='start-assessment']");
            if (start) {
              await start.click();
              await new Promise((r) => setTimeout(r, 1500));
            }
          }
          await new Promise((r) => setTimeout(r, 1200));
          const found = await inspect(page);
          const file = path.join(OUT, `${role}-${sizeKey}-${theme}-${slug(p)}.png`);
          await page.screenshot({ path: file, fullPage: FULL });
          const issues = [...errors];
          if (found.overflow > 1) issues.push(`horizontal overflow ${found.overflow}px`);
          for (const src of found.broken) issues.push(`broken image ${src}`);
          for (const text of found.errorStates) issues.push(`error state: ${text}`);
          if (found.empty) issues.push("page is empty with no explanation");
          if (issues.length) problems.push({ role, page: p, theme, size: sizeKey, issues });
          visited += 1;
          console.log(`${issues.length ? "WARN" : "ok  "} ${role} ${sizeKey} ${theme} ${p}${issues.length ? `: ${issues.join(" | ")}` : ""}`);
        }
        await ctx.close();
      }
    }
  }
  await browser.close();
  await revokeCandidate(ids);
  console.log(`\n${visited} page views, ${problems.length} with problems. Screenshots in ${OUT}`);
  if (problems.length) process.exitCode = 1;
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
