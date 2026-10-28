# High-level design

Euron Open CodeJudge is a self-hosted coding assessment platform. Staff write programming
problems with hidden tests; students, contestants and interview candidates solve them in
the browser in Python, C++, Java or JavaScript; every submission is compiled and run in a
sandbox and comes back with a verdict a person can trust. The same engine serves practice,
timed contests, class assignments and interview screens, and nothing about a submission
leaves the organisation's own servers unless an admin turns on AI hints and points them at
a hosted model.

<p align="center"><img src="../assets/diagrams/architecture.svg" alt="CodeJudge architecture" width="100%"></p>

## Goals and non-goals

| Goals | Non-goals (0.1.0) |
| --- | --- |
| A verdict that is correct, reproducible and impossible for the judged program to influence | Interactive problems (a program talking to a grader), output-only and multi-file submissions |
| Hostile code contained without a privileged container, with judges that hold no database or storage credentials | Kernel-level isolation (gVisor, Kata, Firecracker): see [sandbox.md](sandbox.md) for when you need it |
| Practice, ICPC and IOI contests, class assignments and interview assessments on one engine | Webcam proctoring, identity verification |
| Problems that move between installs and other judges (Kattis package format) | SSO (OIDC, SAML) and LTI: email and password only |
| AI hints that are optional, bring-your-own-model and off by default | Multi-tenant SaaS: one organisation per install |

## Components

| Component | What it does | Where |
| --- | --- | --- |
| Web app (`web`) | Next.js 15: problems and the editor, submissions, contests, classes, assessments, plagiarism, analytics, admin. Proxies `/api/*` to the API so the browser has one origin and a cookie session | `apps/web/` |
| API (`api`) | FastAPI. `/api/v1/*` for the web app and API clients, `/internal/judge/*` for judge workers only. Owns every row | `apps/api/src/codejudge/` (one package per domain) |
| Background worker (`worker`) | Periodic tasks registered by the domains: plagiarism runs, expiring invitations, purging old runs | `codejudge/worker.py`, `core/tasks.py` |
| Judge worker (`judge`) | Takes jobs from the stream, compiles and runs each submission in nsjail, compares output, posts the result. No database, no object storage | `codejudge/judge/`, image `infra/docker/judge.Dockerfile` |
| Postgres | Everything durable: problems, versions, submissions and their per-test results, contests, classes, assessments, audit | RDS on AWS |
| Redis | The judge job stream (required), live verdict events, rate-limit windows, scoreboard cache | ElastiCache on AWS (`noeviction`) |
| Object storage | Test packages by SHA-256, exports | S3 (Floci locally) |
| KMS | Seals the AI provider key; encrypts the bucket | KMS (Floci locally) |
| Mail | Invitation emails | Mailpit locally, SES on AWS |

One Python package holds the API, the background worker and the judge worker. Two images
are built from it: `server.Dockerfile` (API, background worker, CLI, mock AI) and
`judge.Dockerfile` (the same package plus nsjail and the four toolchains). See
[ADR-0007](adr/0007-one-package-two-images.md).

## A submission, end to end

1. The browser posts `POST /api/v1/submissions` with the problem, language, source and
   context (`practice`, `contest`, `assignment` or `assessment`).
2. The API asks the context's policy whether this person may submit now (a contest must be
   running and the person registered; an assignment open and the person a member; an
   assessment within the candidate's deadline). The policy also says whether the
   submission is late and whether its per-test details are hidden.
3. The API writes the submission with a fresh `job_id`, pinned to the problem's current
   test version, and puts a `JudgeJob` on the Redis Stream `judge:jobs`. The job carries
   the source, the limits, the checker, the test list and the package's SHA-256, never
   test data.
4. A judge worker takes the job through the consumer group, fetches the test package from
   `GET /internal/judge/packages/{sha256}` (once; it is cached on the worker and checked
   against the hash), compiles in the sandbox, then runs each test in a fresh sandbox that
   sees only that test's input. Output is compared outside the sandbox.
5. While judging, the worker renews its lease every heartbeat and reports progress
   (`compiling`, `running test 3`), which the API relays to the browser over server-sent
   events.
6. The worker posts the `JudgeResult` to `/internal/judge/results`. The API applies it only
   if it belongs to the submission's current job and the submission is not final yet
   (row lock), then calls every registered listener: contest scoreboards, the analytics
   rollup. The browser gets `done` with the verdict.

Details: [judging.md](judging.md) (queue, leases, idempotency, verdict order),
[sandbox.md](sandbox.md) (isolation and measurement).

## Contexts

A submission's context decides who may make it and who may see it. The submissions domain
asks the policy registered for the context and never imports the domains themselves, so a
contest, a class or an assessment adds rules without touching the judge path.

| Context | Policy | Owner |
| --- | --- | --- |
| `practice` | Published, public problems; staff can submit to anything | `submissions/service.py` |
| `reference` | Staff only: a setter's solution judged on the current tests | `submissions/service.py` |
| `run` | Run on the samples or custom input; never counted, author only, purged after a day | `submissions/service.py` |
| `contest` | Registered participant, contest running, problem in the contest; ICPC hides test details while it runs | [contests.md](contests.md) |
| `assignment` | Class member, assignment open; after the due time accepted, penalised or refused | [classrooms.md](classrooms.md) |
| `assessment` | The invited candidate, before their deadline, problems of their assessment only | [assessments.md](assessments.md) |

## Caching layers

| Layer | What | Key | TTL | Invalidation |
| --- | --- | --- | --- | --- |
| Test packages on the judge | Unpacked packages on the worker's disk (tmpfs in containers) | the package's SHA-256 | none (content addressed); least recently used evicted past `CACHE_MAX_BYTES` | Never needed: a changed test set is a new hash, so a stale package cannot be served |
| Scoreboard | The computed board per contest and view (live or frozen) | contest id, view and the contest's version number | short, bounds memory only | Every verdict, rejudge, problem change or edited window bumps the contest's version key, so a cached board is never served after the data under it changed |
| Analytics rollup | `stats_daily`: counts per day, problem and language | (day, problem, language) | none (a table) | Recomputed from the submissions for that bucket on every judgement, under an advisory lock, so it stays exact through rejudges |
| Problem counters | `submissions_count`, `accepted_count`, `solvers_count` on `problems` | the problem row | none | Updated in the ingest transaction; a rejudge does not count a solve twice |
| Rate limits | Fixed windows for login, sign-up, submissions, hints, candidate events | per IP, user or invitation | the window | Expire on their own |
| HTTP | `Cache-Control: no-store` on test content, exports and anything with hidden data | n/a | n/a | n/a |
| Web | TanStack Query per view; the editor draft in `localStorage` per problem and language | query keys | per query `staleTime` | Mutations invalidate their queries; live verdicts arrive over SSE |

Redis is required in 0.1.0 because the job stream lives there; it runs with
`noeviction` (locally and on AWS) so a queued job is never evicted to make room for a
cache entry.

## Deployment shapes

| Shape | How | Use |
| --- | --- | --- |
| Local, emulated AWS | `make up`: Compose with Floci provisioned by the same Terraform modules | Development, evaluation, the demo |
| Local against real AWS | `make up-aws` with `deploy/compose/.env.aws` | Testing S3, KMS and SES for real |
| AWS | `make aws-deploy`: ECS Fargate (api, worker, web) behind an ALB, the judges on an EC2 capacity provider, RDS, ElastiCache, S3, KMS, SES, CloudWatch | Production |

The judges run on EC2 because Fargate cannot take the custom seccomp profile the sandbox
needs; see [sandbox.md](sandbox.md) and the `judge` Terraform module.

## Scaling

| What | How it scales |
| --- | --- |
| API, background worker, web | Stateless; run N replicas (state in Postgres and Redis) |
| Judges | One sandbox at a time per worker, N workers. Throughput is roughly workers divided by the average judging time; the queue depth is on `/api/v1/judge/queue` and in the alarms |
| Postgres | One query per list, scoreboard and gradebook, indexes on every filter; connection pool sized in config |
| Redis | One stream; consumer groups spread jobs across any number of workers |

## Observability

Structured JSON logs with request ids; Prometheus `/metrics` on the API, the background
worker (port `WORKER_METRICS_PORT`) and each judge (`METRICS_PORT`: jobs by verdict,
judging time); `/healthz` and `/readyz`; optional OpenTelemetry tracing. On AWS, CloudWatch
alarms on 5xx, queue depth and judge internal errors.
