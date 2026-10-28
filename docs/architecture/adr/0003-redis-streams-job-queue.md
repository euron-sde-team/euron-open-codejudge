# ADR-0003: A Redis Stream with a consumer group and leases as the judge queue

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

Judging must not lose a submission when a worker dies, must not count one twice when a
worker retries, and must spread work across any number of workers. Redis is already in the
stack for rate limits and live events.

## Decision

Jobs go on the stream `judge:jobs`, read through the consumer group `judges`. A worker
takes one job, renews its lease by re-claiming its own message every heartbeat, posts the
result, then acknowledges and deletes the message. A job idle longer than the lease is
claimed by another worker (`XAUTOCLAIM`); after three deliveries it is reported as an
internal error. The API applies a result only for the submission's current job and only
once (row lock), so redelivery is harmless. Redis runs with `noeviction`.

## Consequences

**Good**
- At-least-once delivery plus idempotent ingest gives exactly-once verdicts.
- No new service; the queue's depth is `XLEN` and `XPENDING`.

**Bad / caveats**
- Redis is required; the API refuses to submit without it.
- A Redis without persistence loses queued jobs on restart; the local stack uses append-only
  persistence, ElastiCache keeps replicas.

## Alternatives considered

- **Postgres `SKIP LOCKED`**: one less dependency, but polling load and connection use grow
  with workers, and leases need a sweeper.
- **SQS**: fine on AWS, but then local development needs the emulator in the hot path and
  the judges need AWS credentials ([ADR-0005](0005-judges-hold-no-database-or-storage-credentials.md)).
- **Celery or RQ**: more machinery than one stream needs, and less control over leases.
