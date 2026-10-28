# Security

What CodeJudge protects, and how. The judge sandbox has its own document:
[sandbox.md](sandbox.md). The attacks considered are in [threat-model.md](threat-model.md).

## Assets

| Asset | Why it matters |
| --- | --- |
| Hidden tests | If students can read them, every verdict is meaningless |
| Submissions (source code) | Students' and candidates' work; contestants' code during a contest |
| Grades, contest results, assessment reports | Decisions are made on them |
| The judge hosts | They run hostile code by design |
| Accounts and sessions | Staff can publish problems, see every submission and invite candidates |
| Secrets | `SESSION_SECRET`, `INVITE_TOKEN_PEPPER`, `JUDGE_TOKEN`, the master key or KMS key, the AI provider key |

## Controls

### Hidden tests
- Responses to anyone but staff carry only the samples: problem detail has `samples`, never
  `tests`; per-test results show output and checker messages for samples only.
- Test content endpoints (`/problems/{id}/tests/...`, export, admin detail) are staff only
  and `Cache-Control: no-store`.
- The judged program never sees an answer: the package is not mounted in its sandbox, the
  answer is compared outside it ([sandbox.md](sandbox.md)).
- ICPC contest submissions hide per-test results from contestants (no oracle).
- AI hints name a failing hidden test, never show it ([hints.md](hints.md)).

### Running hostile code
- Unprivileged worker container plus nsjail per run, a syscall filter on the program,
  rlimits, no network, no test data, one sandbox per worker ([sandbox.md](sandbox.md)).
- Judges hold `JUDGE_TOKEN` and `REDIS_URL` only: no database, no object storage, no
  session secret ([ADR-0005](adr/0005-judges-hold-no-database-or-storage-credentials.md)).
  They sit on a network that reaches only the API and Redis.
- Test packages are verified against their SHA-256 and unpacked without links, devices,
  absolute paths or `..`.

### Accounts
- Passwords hashed with argon2id, off the event loop; a password policy (at least 10
  characters, upper and lower case, a digit).
- Sign-in throttled per IP (20 per minute) and locked per account for 15 minutes after
  repeated failures (in Postgres, so it holds across replicas).
- Sessions: a signed token in an HttpOnly, SameSite=Lax cookie (`cj_session`, Secure in
  production) or a bearer header for API clients. Signing out records the session id in
  Postgres until it would have expired; changing a password or a role bumps the user's
  session version, ending every other session at once.
- Cookie mutations need `X-CodeJudge-CSRF: 1`, which a cross-site page cannot add without a
  CORS preflight the allowlist refuses.
- Roles (`student`, `staff`, `admin`) are enforced in the API on every route; the web app's
  navigation only mirrors them.

### Candidates
- One-time tokens are stored only as HMAC-SHA256 with `INVITE_TOKEN_PEPPER`; resending
  replaces the token, revoking kills it.
- A candidate token reaches exactly one assessment, until its deadline.

### Input and output
- Request bodies are capped before parsing (2 MB; the package limit only for staff upload
  routes carrying a session).
- Problem statements are rendered as Markdown without raw HTML in the web app; links with
  `javascript:` or `data:` are dropped.
- CSV exports neutralise cells starting with `=`, `+`, `-` or `@`.
- Every rate-limited action (sign-in, sign-up, submissions, hints, candidate events) answers
  429 with `Retry-After`.
- The AI base URL is checked against metadata addresses (and private ones, when
  `AI_ALLOW_PRIVATE_ENDPOINTS` is false).

### Headers
API: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy:
no-referrer`, `Cross-Origin-Opener-Policy: same-origin`, a restrictive `Permissions-Policy`.
Web app: a strict Content-Security-Policy with `frame-ancestors 'none'` and no third-party
script origins (Monaco and KaTeX are bundled).

### Secrets and configuration
- All secrets come from the environment (Secrets Manager on AWS). The AI key is sealed in
  the database (AES-GCM with the master key locally, KMS on AWS) and never returned.
- Production refuses to boot with demo secrets, equal secrets, no Redis, `COOKIE_SECURE`
  off, mail backend `log`, or an AWS endpoint override with `CODEJUDGE_CLOUD=aws`.
- `make sanitize` fails the build on credentials, cloud account ids or em and en dashes in
  committed files.

### Audit
Every change to problems, tests, references, contests, classes, assessments, invitations,
settings, users and rejudges writes an `audit_log` row with the actor, target, details and
IP. Admins read it in the web app.

### Infrastructure (AWS)
Private subnets for every service; TLS at the ALB; RDS, S3 and secrets encrypted with KMS;
least-privilege task roles (the judge's has none); `/internal/*` reachable only from the
judges' security group; IMDSv2 with a hop limit of 1 on the judge instances; checkov in the
gates.

## Reporting

Please report vulnerabilities privately as described in [SECURITY.md](../../SECURITY.md).

## Operator checklist

- Generate every secret randomly (at least 32 characters) and keep them different; set
  `ENVIRONMENT=production`, which refuses to start otherwise.
- Serve over HTTPS and set `COOKIE_SECURE=true`.
- Keep the judges on their own network or security group that reaches only the API and
  Redis, with the judge seccomp profile, every capability dropped, a read-only root and no
  privileged flag. Never mount anything of the worker into a sandbox.
- For a judge open to the public internet, add a kernel boundary (gVisor, Kata) or
  dedicated hosts, and keep the kernel patched.
- Block `/internal/*` at the edge (the AWS Terraform does) so only judges reach it.
- Run Redis with `noeviction` and persistence or replicas.
- Decide on AI hints deliberately: with a hosted model, students' code leaves your servers;
  tell them, or use a local model.
- Back up Postgres and the objects bucket; test a restore.
- Rotate `JUDGE_TOKEN` after any suspected sandbox escape.
- Read the audit log after granting staff or admin roles.
