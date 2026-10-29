/**
 * Curated README screenshots and tour frames from the seeded stack (real data only).
 *
 *   make up && make demo
 *   cd scripts/qa && QA_PASSWORD=... node screenshots.mjs
 *   ../../scripts/qa/make-tour.sh        (stitches the frames into docs/assets/tour.gif)
 *
 * The solve capture is a real submission: the student types a solution into the editor,
 * submits it, and the real judge's verdict arrives live. The candidate capture opens a
 * fresh invitation from Mailpit; that invitation is withdrawn afterwards.
 *
 * Writes docs/assets/screenshots/NN-name.png and scripts/qa/output/tour/NN.png.
 */
import { mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.QA_BASE ?? "http://localhost:4710";
const MAILPIT = process.env.QA_MAILPIT ?? "http://localhost:4725";
const PASSWORD = process.env.QA_PASSWORD ?? process.env.CJ_DEMO_PASSWORD ?? "";
const SHOTS = path.resolve(HERE, "../../docs/assets/screenshots");
const TOUR = path.resolve(HERE, "output/tour");
const CHROME = process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH) ? process.env.CHROME_PATH : undefined;
const DESKTOP = { width: 1440, height: 900, deviceScaleFactor: 1 };
const PHONE = { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 };

const ADMIN = "admin@codejudge.local";
const TEACHER = "priya.raman@codejudge.local";
const INTERVIEWER = "daniel.okafor@codejudge.local";
const STUDENT = "aarav.mehta@students.example";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let tourIndex = 0;

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

async function settle(page, ms = 1200) {
  await page.waitForNetworkIdle({ idleTime: 400, timeout: 20_000 }).catch(() => {});
  await sleep(ms);
}

/** A curated shot, plus a viewport-sized tour frame (all tour frames share one size). */
async function shot(page, name, { tour = true, fullPage = false } = {}) {
  await page.mouse.move(1, 1); // no hover tooltip in a capture
  await sleep(250);
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage });
  if (tour) {
    await page.screenshot({
      path: path.join(TOUR, `${String(++tourIndex).padStart(2, "0")}.png`),
      clip: { x: 0, y: 0, width: DESKTOP.width, height: DESKTOP.height },
    });
  }
  console.log(`saved ${name}`);
}

async function open(page, url, ms = 1500) {
  await page.goto(`${BASE}${url}`, { waitUntil: "networkidle2", timeout: 60_000 });
  await settle(page, ms);
}

async function session(browser, email, { theme = "light", viewport = DESKTOP } = {}) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport(viewport);
  await page.evaluateOnNewDocument((t) => {
    try {
      localStorage.setItem("theme", t);
    } catch {}
  }, theme);
  if (email) {
    await page.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
    await page.type("#email", email);
    await page.type("#password", PASSWORD);
    await Promise.all([page.waitForNavigation({ waitUntil: "networkidle2" }), page.click("button[type=submit]")]);
  }
  return { ctx, page };
}

async function clickText(page, selector, text) {
  for (const el of await page.$$(selector)) {
    if (((await el.evaluate((e) => e.textContent)) ?? "").trim() === text) {
      await el.click();
      return;
    }
  }
  throw new Error(`no ${selector} with text ${text}`);
}

/** Replace the editor's code: clear it, then hand Monaco a paste event carrying the code.
 * A paste lands as-is, where typed characters would go through auto-indent. */
async function typeCode(page, code) {
  await page.click(".monaco-editor .view-lines");
  for (const mod of ["Meta", "Control"]) {
    await page.keyboard.down(mod);
    await page.keyboard.press("KeyA");
    await page.keyboard.up(mod);
    await page.keyboard.press("Backspace");
    if (!(await page.$eval(".monaco-editor .view-lines", (e) => e.textContent?.trim() ?? ""))) break;
  }
  await page.$eval(
    ".monaco-editor textarea",
    (el, text) => {
      const data = new DataTransfer();
      data.setData("text/plain", text);
      el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true, cancelable: true }));
    },
    code,
  );
  await sleep(400);
  // Monaco renders spaces as non-breaking spaces: compare with plain ones.
  const text = (await page.$eval(".monaco-editor .view-lines", (e) => e.textContent ?? "")).replace(/\u00a0/g, " ");
  if (!text.includes(code.split("\n")[1].trim()) || text.includes("read the input, solve")) {
    throw new Error("the code did not reach the editor");
  }
}

async function waitText(page, text, timeout = 90_000) {
  await page.waitForFunction((t) => document.body.innerText.includes(t), { timeout }, text);
}

async function inviteLink(email) {
  for (let i = 0; i < 30; i++) {
    const found = await (await fetch(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`)).json();
    if (found.messages?.length) {
      const msg = await (await fetch(`${MAILPIT}/api/v1/message/${found.messages[0].ID}`)).json();
      const m = /\/take\/([A-Za-z0-9_-]+)/.exec(`${msg.Text} ${msg.HTML}`);
      if (m) return `/take/${m[1]}`;
    }
    await sleep(1000);
  }
  throw new Error("the invitation email never reached Mailpit");
}

const GRID_ESCAPE = `import sys
from collections import deque

def main() -> None:
    data = sys.stdin.read().split()
    n, m = int(data[0]), int(data[1])
    grid = data[2:2 + n]
    dist = [[-1] * m for _ in range(n)]
    dist[0][0] = 0
    queue = deque([(0, 0)])
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < n and 0 <= nx < m and grid[ny][nx] == "." and dist[ny][nx] < 0:
                dist[ny][nx] = dist[y][x] + 1
                queue.append((ny, nx))
    print(dist[n - 1][m - 1])

main()
`;

async function main() {
  await mkdir(SHOTS, { recursive: true });
  await mkdir(TOUR, { recursive: true });
  const adminToken = await token(ADMIN);
  const ids = await (async () => {
    const classes = await api(adminToken, "GET", "/api/v1/classes");
    const klass = classes.find((c) => c.name.startsWith("CS201"));
    const assignments = await api(adminToken, "GET", `/api/v1/classes/${klass.id}/assignments`);
    const week3 = assignments.find((a) => a.title.startsWith("Week 3"));
    const assessments = await api(adminToken, "GET", "/api/v1/assessments");
    const screen = assessments.find((a) => a.title.startsWith("Backend"));
    const invitations = await api(adminToken, "GET", `/api/v1/assessments/${screen.id}/invitations`);
    const jordan = invitations.find((i) => i.name === "Jordan Lee");
    const runs = await api(adminToken, "GET", "/api/v1/plagiarism/runs");
    const run = await api(adminToken, "GET", `/api/v1/plagiarism/runs/${runs[runs.length - 1].id}`);
    // The planted pair: a copy with renamed variables and reordered code, not identical text.
    const pair = run.pairs.find((p) => p.language === "python3") ?? run.pairs[0];
    const ranges = (await api(adminToken, "GET", "/api/v1/problems?q=range-sums")).items[0];
    // A classic wrong algorithm: greedy coin change.
    const wrong = (await api(adminToken, "GET", "/api/v1/submissions?verdict=WA&problem=coin-change&limit=1")).items[0] ?? null;
    return { week3: week3.id, screen: screen.id, jordan: jordan.id, pair: pair.id, ranges: ranges.id, wrong: wrong?.id };
  })();

  const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-sandbox"] });

  // 01 Problems and 02 Solve, as a student.
  {
    const { ctx, page } = await session(browser, STUDENT);
    await open(page, "/problems");
    await shot(page, "01-problems");
    await page.setViewport({ ...DESKTOP, height: 1180 });
    await open(page, "/problems/grid-escape", 2500);
    await typeCode(page, GRID_ESCAPE);
    await clickText(page, "button", "Submit");
    await waitText(page, "Accepted").catch(async (e) => {
      await page.screenshot({ path: path.join(TOUR, "..", "solve-failed.png"), fullPage: true });
      throw e;
    });
    // Let the "Submitted" toast go before the capture.
    await settle(page, 5000);
    await shot(page, "02-solve");
    await ctx.close();
  }

  // 03 Submission, 04 Scoreboard, 07 Problem editor, 08 Plagiarism, 09 Analytics: staff.
  {
    const { ctx, page } = await session(browser, ADMIN);
    if (ids.wrong) {
      await open(page, `/submissions/${ids.wrong}`);
      await shot(page, "03-submission");
    }
    await open(page, "/contests/autumn-sprint-2026?tab=scoreboard");
    await shot(page, "04-scoreboard");
    await open(page, `/manage/problems/${ids.ranges}?tab=tests`);
    await shot(page, "07-problem-editor");
    await open(page, `/plagiarism/pairs/${ids.pair}`);
    await shot(page, "08-plagiarism");
    await open(page, "/analytics", 2500);
    await shot(page, "09-analytics");
    await ctx.close();
  }

  // 05 Gradebook, as the teacher.
  {
    const { ctx, page } = await session(browser, TEACHER);
    await open(page, `/assignments/${ids.week3}?tab=gradebook`);
    await shot(page, "05-gradebook");
    await ctx.close();
  }

  // 06 Interview report, as the interviewer.
  {
    const { ctx, page } = await session(browser, INTERVIEWER);
    await open(page, `/assessments/${ids.screen}/invitations/${ids.jordan}`);
    await shot(page, "06-interview-report");
    await ctx.close();
  }

  // 10 Candidate: a fresh invitation, opened from its email, started; withdrawn afterwards.
  {
    const interviewerToken = await token(INTERVIEWER);
    const email = `taylor.reed.${Date.now().toString(36)}@example.com`;
    await api(interviewerToken, "POST", `/api/v1/assessments/${ids.screen}/invitations`, { candidates: [{ email, name: "Taylor Reed" }] });
    const link = await inviteLink(email);
    const { ctx, page } = await session(browser, null);
    await open(page, link);
    await clickText(page, "button", "Start the assessment");
    await settle(page, 2000);
    await shot(page, "10-candidate");
    await ctx.close();
    const list = await api(interviewerToken, "GET", `/api/v1/assessments/${ids.screen}/invitations`);
    const inv = list.find((i) => i.email === email);
    if (inv) await api(interviewerToken, "POST", `/api/v1/assessments/${ids.screen}/invitations/${inv.id}/revoke`);
  }

  // 11 Dark mode: the live contest scoreboard.
  {
    const { ctx, page } = await session(browser, STUDENT, { theme: "dark" });
    await open(page, "/problems/longest-increasing", 2500);
    await shot(page, "11-dark-mode");
    await ctx.close();
  }

  // 12 Phone: the problem list as a student.
  {
    const { ctx, page } = await session(browser, STUDENT, { viewport: PHONE });
    await open(page, "/problems");
    await shot(page, "12-mobile", { tour: false });
    await ctx.close();
  }

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
