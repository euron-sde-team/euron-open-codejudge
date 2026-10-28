# Low-level design

How the code is laid out and how a request moves through it. The big picture is in
[HLD.md](HLD.md); the judge path in [judging.md](judging.md) and [sandbox.md](sandbox.md).

## Package layout

```text
apps/api/src/codejudge/
  core/          config (validated settings, production guards), container (process-wide
                 services), db, kv (Redis or in-process), queue (job stream, SSE events),
                 contract (API <-> judge), contexts (submission policies and listeners),
                 tasks (periodic task registry), errors, middleware, security, sealing,
                 storage (disk or S3), mail, net (SSRF checks), logs, tracing
  auth/ users/ audit/ org/        sign-in, roles, audit log, settings and sign-up
  problems/      models, schemas, service (lifecycle, versions, publish gate), packages
                 (Kattis build, parse, export), router
  submissions/   models, schemas, service (admit, dispatch, ingest, rejudge), router
                 (public and /internal/judge), tasks (purge runs)
  judge/         the worker side: languages (registry + languages.yaml), sandbox (nsjail),
                 runner (compile, run, classify, check, score), checkers, packages
                 (fetch, verify, unpack, cache), worker (stream loop, leases, heartbeats)
  contests/ classrooms/ assessments/ plagiarism/ analytics/ hints/
  demo/          the demo seed and its problem set
  migrations/    Alembic
  main.py        create_app(): routers, middleware, lifespan
  worker.py      the background worker loop
  cli.py         codejudge serve | judge | worker | migrate | create-admin | seed-demo | openapi
```

Dependencies point inward: router to service to models. A domain calls another domain's
service, never its tables. Two registries keep the submission path independent of the
domains that use it:

- `core/contexts.py`: each context registers a `ContextPolicy` (`admit`, `can_view`) and
  any number of `on_judged` listeners. `submissions/service.py` asks the policy and calls
  the listeners; it imports no contest, class or assessment code.
- `core/tasks.py`: domains register periodic tasks with `@periodic(name)`; `worker.py`
  imports their modules and runs every task on each tick.

## A request

1. `RequestContextMiddleware` assigns a request id, adds the security headers and logs one
   line. `BodySizeLimitMiddleware` refuses large bodies before any route parses them
   (2 MB in general; the package limit for staff upload routes; a larger limit for
   `/internal`).
2. Dependencies resolve the caller: `current_user` (bearer token or the `cj_session`
   cookie, with the CSRF header on cookie mutations), `current_submitter` (a user or an
   interview candidate from `X-CodeJudge-Candidate`), or `judge_only` (the judge token,
   compared in constant time). Role dependencies: `Student`, `Staff`, `Admin`.
3. The service runs the rules; `AppError` subclasses become one JSON shape:
   `{"error": {"code", "type", "message", "details"}}`, with a status per class.

## The container

`Container.build(settings)` creates the database engine, the KV store (Redis or in
process), the judge queue (Redis), the HTTP client for the AI provider, the sealer (local
AES-GCM or KMS) and the object storage (disk or S3), once per process, on `app.state`.
Tests build their own app and container.

## The judge worker process

Synchronous, one job at a time: `Worker.run` loops `next_message` (reclaim, then read),
`process` (attempt count, heartbeat thread, `Judge.judge`, post, acknowledge). `Judge`
creates a work directory per job attempt under `WORK_DIR`, writes the source, compiles,
fetches the package through `PackageCache`, runs tests with `Sandbox.run`, and removes the
work directory whatever happens.

`Sandbox.run` builds the nsjail command line (namespaces, mounts, rlimits, the syscall
policy, the environment), starts it in its own process group behind
`sh -c 'echo 1000 > /proc/self/oom_score_adj; exec ...'`, waits with `os.wait4` (a timer
kills the group if nsjail itself hangs), and returns exit code, signal, CPU time, wall time,
peak memory, output size and nsjail's log.

## Languages

`judge/languages.yaml` is read by both the API (to list languages and their editor
templates) and the judge (to build commands), so a language the API offers is one the judge
can run. Each entry: source file name, compile and run commands with `{src}`, `{mem}`,
`{stack}` placeholders, `memory_mode` (`address` or `rss`) with an overhead, a time factor,
the number of threads allowed, extra environment, the Monaco language id and a template.
Adding a language is a toolchain in the judge image plus one entry.

| Language | Compile | Run | Memory |
| --- | --- | --- | --- |
| `python3` (Python 3.13) | `ast.parse` (syntax check) | `python3 -S -B main.py` | address space |
| `cpp17` (GCC) | `g++ -O2 -std=gnu++17` | `./main` | address space |
| `java21` (OpenJDK 21) | `javac` | `java -Xmx<mem>m -XX:+UseSerialGC -XX:TieredStopAtLevel=1 Main` | heap flag + peak RSS |
| `javascript` (Node.js) | `node --check` | `node --max-old-space-size=<mem>` | heap flag + peak RSS |

## The web app

`apps/web/src/`: `app/` holds routes only; `features/<domain>/` holds each domain's
components, hooks and API calls; `components/ui/` the shadcn primitives; `lib/` the API
client (types generated from `docs/api/openapi.yaml` with openapi-typescript), formatting
and helpers. Server state goes through TanStack Query hooks per feature. The browser talks
only to the web app's origin; `/api/*` is proxied to the API with the session cookie, and
mutations add `x-codejudge-csrf: 1`. The editor is Monaco, bundled locally (no CDN), with
drafts per problem and language in `localStorage`.
