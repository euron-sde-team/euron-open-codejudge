# Euron Open CodeJudge: plan for 0.1.0

Source brief: `euron-open-source/briefs/07-codejudge.md`. Scope decision (user, 2026-10-28):
"as good as it can get", so 0.1.0 covers the brief's whole module table, built to the same
bar as the core: nothing ships that does not pass every gate.

## Purpose

CodeJudge is a self-hosted coding assessment platform for universities, bootcamps,
interviewers, competitive programming clubs and companies. A teacher, interviewer or
contest organiser writes a programming problem with test data; people solve it in the
browser in Python, C++, Java or JavaScript; CodeJudge compiles and runs every submission
in an isolated sandbox and returns a **trustworthy verdict** (Accepted, Wrong Answer, Time
Limit Exceeded, Memory Limit Exceeded, Runtime Error, Compilation Error, Output Limit
Exceeded) within seconds. It removes two problems: paying a SaaS per candidate or per
submission, and sending students' and candidates' code to a third party. The outcome it
guarantees: **hostile code cannot escape, slow down other submissions, or read the hidden
tests, and the same program always receives the same verdict.**

The name is the contract. A *judge* must (1) decide correctly, (2) decide the same way
every time, (3) never be fooled or harmed by the code it judges, and (4) never leak the
answers.

## Comparable products and what users expect

| Product | Kind | Licence | Notes |
| --- | --- | --- | --- |
| HackerRank, Codility, CodeSignal | SaaS assessment | proprietary | Per seat/attempt pricing (HackerRank lists $199 to $449/month plus $20 per extra attempt); proctoring, plagiarism, candidate reports |
| Judge0 | code execution API | GPL | Execution only, no problems/contests. 2024: three CVSS 9 to 10 sandbox escapes (CVE-2024-28185, -28189, -29021) became host root because workers run `--privileged` |
| DMOJ | contest judge | AGPL | ptrace + rlimit sandbox, many languages, Django |
| DOMjudge | ICPC contest judge | GPL | Mature ICPC tooling, PHP |
| CMS | IOI contest system | AGPL | isolate sandbox, subtasks |
| Kattis problemtools / Problem Package Format | format | open | The interchange format DOMjudge and Kattis use |

Expected by users of this category: in-browser editor with sample runs, precise CPU and
memory limits, hidden tests, subtasks/partial score, rejudge, ICPC and IOI scoreboards
with freeze, plagiarism detection, candidate invitations and reports, problem import and
export, multiple workers.

**Why ours is worth starring:**

1. **A sandbox that needs no privileged container.** Workers run with every Linux
   capability dropped, `no-new-privileges`, Docker's default seccomp profile plus only the
   namespace syscalls, and nsjail creates a fresh user, PID, network, mount, IPC and UTS
   namespace per run, with a second syscall filter on the submission itself. A sandbox
   escape lands as an unprivileged user inside an unprivileged container with no network,
   not as root on the host (the Judge0 failure mode). Proven by a prototype on 2026-10-28
   (see "Sandbox design"), and by the hostile-code acceptance suite on every run.
2. **Workers never hold database credentials** and never see answers while a submission
   runs: the sandbox gets the input only; output is compared outside it.
3. **Portable problems** in the open Kattis/ICPC Problem Package Format, so problems move
   between CodeJudge, DOMjudge and Kattis.
4. **Modern, privacy-first, no per-submission cost**, AI optional and bring-your-own-model,
   with zero LLM calls by default.

## Acceptance criteria (each one is an automated test)

| # | Criterion | Test |
| --- | --- | --- |
| AC1 | Correct solutions are Accepted; each failure class gets its verdict: WA (with the first failing test), TLE, MLE, RE, CE, OLE, in Python, C++, Java and JavaScript | integration: verdict matrix, fixtures per language |
| AC2 | Hostile code is contained and the worker survives: network, writes outside the box, reading other files or test answers, fork bomb, memory bomb, output flood, sleeping forever, ptrace, unshare, kill of the worker; the next submission is judged correctly | integration: hostile suite against the real worker image |
| AC3 | Hidden tests never leak: no API response to a contestant contains hidden input or answers; the sandbox never sees the answer file | integration + unit |
| AC4 | Verdicts are reproducible: rejudging gives the same verdict; time is CPU time, so a busy machine does not turn AC into TLE within the documented margin | integration: rejudge, load test |
| AC5 | A worker that crashes mid-job does not lose or double-count the submission: the job is reclaimed and judged exactly once | integration: kill a worker mid-run |
| AC6 | Problems round-trip: export as a Kattis package and import gives the same problem; the official Kattis sample packages import; a problem cannot be published until its reference solution is Accepted | integration |
| AC7 | Contest scoreboards are correct: ICPC (solved, penalty minutes, 20 per wrong try) and IOI (best score per subtask); the freeze hides results from contestants until unfrozen; submissions outside the contest window are refused | unit (scoring) + integration + e2e |
| AC8 | Classroom: a student in a class sees its assignments; a submission after the deadline is marked late (or refused when late work is off); the teacher's report exports as CSV | integration + e2e |
| AC9 | Interview: an invited candidate with no account opens a one-time link, takes a timed assessment, cannot continue after the time is up, and the interviewer gets a report with scores, code and timeline | integration + e2e |
| AC10 | Plagiarism: a copy with renamed variables and reordered functions is flagged; an independent solution to the same problem is not | unit + integration |
| AC11 | AI is optional: with AI off (the default) no LLM request is ever made; with it on, hints never include hidden test data and are disabled inside contests and assessments | integration with a mock LLM |
| AC12 | Throughput and isolation under load: N submissions in parallel across workers all get correct verdicts; one hostile submission does not change another's verdict | integration |
| AC13 | A developer can clone, `make up && make demo`, create a problem, submit and get a verdict, all in the browser | e2e (the five-minute path) |

## Scope of 0.1.0

**In:** problems (statement in Markdown with math, limits, tags, difficulty, test groups
with points, sample/hidden tests, custom checkers, reference solutions, versions),
import/export (Kattis package format, zip), the judge (queue, workers, sandbox, verdicts,
partial scoring, rejudge), the editor (Monaco, language picker, run on samples and custom
input, submit, live verdict), accounts and roles (admin, staff, student; organisation
settings), contests (ICPC and IOI, schedule, registration, scoreboard with freeze,
clarifications), classroom (classes, rosters by invite code, assignments with deadlines and
late policy, gradebook, CSV), interview (assessments, email invitations with one-time
links, time limit, candidate reports, paste and tab-away events recorded and shown
honestly as signals, not proof), analytics (acceptance, verdict mix, difficulty, per-user
progress, pre-aggregated), plagiarism (token winnowing per language, pair report with
side-by-side diff), optional AI hints (OpenAI-compatible endpoint, local or hosted, off by
default), audit log, Docker Compose, backups (`make backup` / `make restore`), Terraform
for AWS.

**Roadmap (not 0.1.0):** more languages (Go, Rust, Kotlin), interactive problems,
output-only and multi-file submissions, virtual contests, SSO (OIDC/SAML), webcam
proctoring, LTI for LMS integration.

## Architecture

```
browser (Next.js 15, Monaco)
   |  HTTPS
api (FastAPI) ------ Postgres (problems, submissions, verdicts, contests, classes, audit)
   |   \------------ Redis (job stream, scoreboard cache, rate limits, SSE fan-out)
   |   \------------ S3 (test data packages by content hash, exports, backups)
   |
   |  Redis Streams: judge jobs (consumer group, ack, reclaim)
   v
judge worker (Python, one sandbox at a time, N replicas)
   |-- fetches test data by content hash from the API's internal endpoint (no DB, no S3 creds)
   |-- compiles and runs inside nsjail (per run namespaces, rlimits, syscall filter)
   |-- compares output outside the sandbox (exact, token, float tolerance, custom checker in its own sandbox)
   '-- posts results to the API's internal endpoint (token, idempotent per job attempt)
```

Domains (`apps/api/src/codejudge/`): `core`, `auth`, `users`, `org` (settings), `problems`
(statements, tests, checkers, packages), `submissions`, `judge` (dispatch, ingest, rejudge,
internal endpoints), `contests` (scoring, scoreboard, freeze, clarifications), `classrooms`,
`assessments` (interview), `analytics`, `plagiarism`, `hints` (AI), `audit`, `demo`.
Judge worker: `apps/judge/src/codejudge_judge/` (`sandbox`, `languages`, `checkers`,
`runner`, `client`). Languages are a registry file (`languages.yaml`): compile and run
commands, file names, time and memory multipliers, so adding a language is a toolchain in
the image plus one entry.

## Sandbox design (prototype results, 2026-10-28, Docker Desktop, linuxkit 6.12, arm64)

Outer layer, the worker container: `cap_drop: ALL`, `no-new-privileges`, read-only root,
a seccomp profile equal to Docker's default plus `clone, unshare, mount, umount2,
pivot_root, sethostname, setdomainname, setns` (no capability needed; the kernel only
allows them inside the new user namespace), `pids_limit`, memory limit, no published
ports, on a network that reaches only the API's internal endpoint and Redis.

Inner layer, per run (nsjail 3.6, built from source at a pinned tag): new user, PID, net
(no interfaces), mount, IPC, UTS namespaces; runs as uid 65534; filesystem is read-only
`/usr /lib /bin` plus a fresh writable box; no `/proc`; rlimits on CPU, address space,
processes, file size, open files; a wall clock limit; a kafel syscall filter on the
program: `unshare setns mount umount pivot_root ptrace process_vm_* bpf keyctl add_key
request_key perf_event_open userfaultfd io_uring_setup` fail with EPERM, `clone3` with
ENOSYS (so threads fall back to `clone`).

Measured: ptrace and unshare refused (EPERM); no network and no DNS; `/usr` read-only;
`/etc/shadow` absent; fork bomb stopped at the process limit; memory bomb stopped at the
cap; infinite loop killed at the CPU limit; output flood capped; CPU time from `wait4`
rusage is linear (10M iterations 0.36 s, 20M 0.75 s) and excludes sleep (1 s sleep, 0.01 s
CPU); peak memory accurate (100 MB touched reads 106 MB); sandbox start-up about 8 ms.

Not cgroups: they need a privileged or cgroup-delegated container. Limits come from rlimits
(the DMOJ approach) inside the container's own memory and pids limits. One sandbox per
worker process keeps per-uid process limits exact; throughput scales with replicas.

AWS: Fargate cannot take a custom seccomp profile, so judge workers run on ECS with an EC2
capacity provider (an Auto Scaling group); api, web and the background worker stay on
Fargate.

## Data model (main tables)

`users`, `org_settings`, `problems` (slug, title, statement_md, limits, checker,
visibility, status draft/published, current_version), `problem_versions` (package hash in
S3, test groups with points, sample flags), `submissions` (user, problem, version,
language, source, status, verdict, score, time_ms, memory_kb, context: practice / contest
/ assignment / assessment), `submission_tests` (per test verdict, time, memory, no output
stored for hidden tests), `judge_jobs` (attempts, lease), `contests`, `contest_problems`,
`contest_participants`, `clarifications`, `classes`, `class_members`, `assignments`,
`assessments`, `invitations` (hashed token, window), `candidate_events`,
`plagiarism_runs`, `plagiarism_pairs`, `hint_requests`, `stats_daily` (rollups),
`audit_log`.

## Screens

Sign in; Problems (list, filters, solved marks); Problem (statement, editor, run on
samples or custom input, submit, verdict with per test table); Submissions; Contests (list,
contest page with problems and timer, scoreboard, clarifications); Classes (student and
teacher views, gradebook); Assessments (interviewer list, invite, candidate report;
candidate take page with timer); Problem editor (statement preview, tests upload, test
groups and points, reference solutions with their verdicts, publish); Import/export;
Plagiarism; Analytics overview; Users; Settings (languages, limits, AI, email); Audit.

## Terraform modules

`network`, `database` (RDS), `cache` (ElastiCache), `storage` (S3), `kms`, `secrets`,
`ecr`, `service` (ECS Fargate behind an ALB: api, web, background worker), `judge` (ECS on
EC2 capacity provider with the worker's seccomp profile and capability drop), `email` (SES
for invitations), `observability` (CloudWatch logs, alarms on queue depth and judge
errors). Envs: `local-floci`, `aws-dev`, `aws-prod`.

## Ports (project 07)

web 4710, api 4730, mailpit UI 4725, postgres 4742, mock LLM 4750, floci 4766, redis 4779,
tf-aws-on-floci 4796.

## Test plan

Unit: scoring (ICPC, IOI, freeze), checkers (token, float, exact), verdict classification
from exit status and rusage, Kattis package parsing, winnowing, redaction, permissions.
Integration (real Postgres, Redis, Floci, the real worker image): every endpoint and role,
the verdict matrix in four languages, the hostile suite, crash and redelivery, rejudge,
import/export, contests, classes, assessments, plagiarism, hints with a mock LLM. Matrix:
storage local and S3, Redis on and off for caches. E2E (Playwright): the five-minute path,
solve in the editor, contest with live scoreboard, class assignment, candidate assessment,
import/export. Browser QA (Puppeteer): every page, light and dark, desktop and phone.
Infrastructure: validate, tflint, checkov, tf-aws-on-floci. Benchmarks: judge throughput
(submissions per minute per worker), queue latency, sandbox overhead.
