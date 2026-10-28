# Data model

PostgreSQL 16, SQLAlchemy 2 models per domain, Alembic migrations. Timestamps are
timezone-aware. Every list the API exposes filters and sorts on an index.

## Problems and judging

| Table | Holds | Notes |
| --- | --- | --- |
| `problems` | slug (unique), title, statement, difficulty, tags, limits, checker, status (`draft`/`published`), visibility (`public`/`private`), source, license, current version, author, counters (`submissions_count`, `accepted_count`, `solvers_count`) | The counters are denormalised for the problem list and updated in the ingest transaction |
| `problem_versions` | problem, number, package SHA-256 and size, tests (name, group, sample, sizes), groups (name, points, stop on failure), public samples, checker, max score, note | Immutable; the package itself is in object storage under `packages/<sha256>.zip` |
| `reference_solutions` | problem, name, language, source, expected verdict, last submission | The publish gate |
| `submissions` | user or candidate, problem, version, language, source, context and context id, status (`queued`/`judging`/`done`), verdict, score and max, time, memory, compile output, per-test and per-group results, run input and output, `late`, `hide_test_details`, `job_id` (unique), attempt, worker, progress, error, judging time, rejudge count, created and judged times | Indexes: (user, created), (problem, created), (context, context id, created), job id, and a partial index on unfinished statuses |

Per-test results never contain hidden test content: the worker returns output and checker
messages only for samples.

## People and settings

| Table | Holds |
| --- | --- |
| `users` | email (unique), name, argon2id hash, role (`student`/`staff`/`admin`), disabled, last login, failed logins, locked until, session version |
| `revoked_sessions` | signed-out session ids until they would have expired (Postgres, never a cache, so eviction cannot bring one back) |
| `org_settings` | one row: site name, sign-up, default language, AI settings with the sealed key |
| `audit_log` | who did what to which target, with details and IP |

## Contests

| Table | Holds |
| --- | --- |
| `contests` | slug, title, description, format, window, freeze, unfrozen, visibility, registration, join code, penalty minutes |
| `contest_problems` | contest, problem, label, position, points |
| `contest_participants` | contest, user, registered at (unique pair) |
| `clarifications` | contest, problem label, question, answer, public, who asked and answered |

## Classes

| Table | Holds |
| --- | --- |
| `classes` | name, description, join code, archived |
| `class_members` | class, user, role (`teacher`/`student`), joined at |
| `assignments` | class, title, description, opens and due times, late policy, penalty percent |
| `assignment_problems` | assignment, problem, points, position |
| `assignment_extensions` | assignment, user, due time |

## Assessments

| Table | Holds |
| --- | --- |
| `assessments` | title, instructions, duration, window |
| `assessment_problems` | assessment, problem, points, position |
| `invitations` | assessment, email, name, token HMAC, status, sent, started, deadline, submitted, events count |
| `candidate_events` | invitation, kind (`paste`, `tab_hidden`, `tab_visible`, `started`, `submitted`), detail, time |

## Plagiarism, analytics, hints

| Table | Holds |
| --- | --- |
| `plagiarism_runs` | scope and scope id, threshold, status, programs, comparisons, flagged, error, timing |
| `plagiarism_pairs` | run, problem, language, the two submissions, similarity, coverage per side, matched line ranges per side |
| `stats_daily` | day, problem, language, submissions, accepted, counts per failure verdict, users |
| `hint_requests` | user, problem, submission, context, model, status, token counts, error |

## Object storage

| Key | Holds |
| --- | --- |
| `packages/<sha256>.zip` | A problem version's test package (content addressed, written once) |

Rows keep only the hash; blobs never go into the database.
