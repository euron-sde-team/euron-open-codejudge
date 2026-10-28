# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-28

First public release: the judge and its sandbox, the API, the web app, contests, classes,
interview assessments, plagiarism checks, analytics and optional AI hints.

### Added

- A judge worker that compiles and runs submissions in Python 3, C++17 (GCC), Java 21 and
  JavaScript (Node.js), each run in a fresh nsjail sandbox (user, PID, network, mount, IPC
  and UTS namespaces, rlimits, a syscall filter on the program, no network, no `/proc`, no
  test data), inside a worker container with every capability dropped.
- Verdicts AC, WA, TLE, MLE, RE, CE, OLE and IE decided from measured CPU time, peak
  memory and output size, in a fixed order; CPU time is measured, so a busy machine does
  not turn accepted solutions into time limits.
- Checkers: tokens (the default), floats with tolerances, exact lines, and custom checkers
  in any judge language with the Kattis or testlib exit code conventions.
- Test groups with points (IOI style partial scoring) and stop on first failure.
- A Redis Stream job queue with a consumer group, leases renewed by heartbeats,
  redelivery to another worker when one dies, and a give-up after three deliveries.
  Results are applied exactly once (current job only, row lock), so retries and
  redeliveries are harmless.
- Problems with Markdown and math statements, tags, difficulty, limits, public and private
  visibility, versioned tests in the Kattis problem package format (import, export,
  deterministic builds), reference solutions with expected verdicts, and a publish gate
  that requires them all to pass.
- Run on samples and on custom input, live verdicts over server-sent events, rejudging on
  the original or the current tests.
- Contests: ICPC (solved, penalty minutes) and IOI (best score per problem) scoreboards,
  a freeze with unfreeze, registration (open or by code), private problems, clarifications
  and announcements; the board computed with a fixed number of queries and cached until
  the next change.
- Classes: join codes, rosters, assignments with opening and due times, late policies
  (accept, penalty, refuse), extensions, a gradebook with CSV export.
- Interview assessments: email invitations with one-time links, a timed session for
  candidates without accounts, paste and tab-away signals, and a report with scores, code
  and the timeline.
- Plagiarism checks by winnowing over normalised tokens (Python, C++, Java, JavaScript),
  as background runs per problem, contest or assignment, with side-by-side matched ranges.
- Analytics: a daily rollup kept exact by recomputing one bucket per judgement; overview,
  per-problem and per-user progress pages.
- Optional AI hints through any OpenAI-compatible endpoint, off by default, never in
  contests or assessments, capped per problem.
- Roles (student, staff, admin), self sign-up for students (switchable), organisation
  settings, an audit log.
- The web app: problems and the Monaco editor (bundled, no CDN), submissions, problem
  editor and import, contests, classes, assessments and the candidate page, plagiarism,
  analytics, admin; light and dark, down to phone width.
- Docker Compose for the whole stack with Floci (S3, KMS, Secrets Manager) provisioned by
  the same Terraform as production, Mailpit for invitations, a mock language model.
- Terraform for AWS: VPC, RDS, ElastiCache (`noeviction`), S3, KMS, Secrets Manager, ECR,
  SES, ECS Fargate for api, worker and web behind an ALB, the judges on an EC2 capacity
  provider with the sandbox's seccomp profile, CloudWatch alarms.
- A demo seed with twelve problems judged for real, contests, a class, an interview and a
  month of history derived from real verdicts.

### Security

- The judge worker container is never privileged: Docker's default seccomp profile plus
  only the namespace calls nsjail needs, `no-new-privileges`, read-only root, and a network
  that reaches only the API and Redis.
- Judge workers hold only the judge token and the Redis URL: no database, storage or
  session secrets. On AWS their task role has no permissions and instance metadata is
  blocked.
- Hidden tests never reach the program's sandbox, a non-staff response, or an AI prompt;
  ICPC contests hide per-test results from contestants.
- Test packages are verified by SHA-256 and unpacked without links, devices or path
  traversal.
- Invitation tokens stored only as HMACs; argon2id passwords, lockout and throttling; CSRF
  header on cookie mutations; production refuses unsafe configuration.
