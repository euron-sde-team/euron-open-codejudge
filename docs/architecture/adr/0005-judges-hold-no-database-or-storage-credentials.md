# ADR-0005: Judge workers hold no database or storage credentials

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

The judge is the component most likely to be compromised: it runs hostile code. Whatever it
holds, an attacker who escapes the sandbox holds too.

## Decision

A judge worker gets two secrets: `JUDGE_TOKEN` (for `/internal/judge/*` on the API) and
`REDIS_URL` (the job stream). It fetches test packages from the API by hash and posts
results to the API. It has no database URL, no object storage credentials, no session
secret and, on AWS, a task role with no policy. Its network reaches only the API and Redis.

## Consequences

**Good**
- An escape cannot read or change grades, submissions or accounts directly, or read test
  packages for problems it was not asked to judge.
- The API validates every result (current job, once) before it touches a row.

**Bad / caveats**
- The judge token can post results for jobs readable from Redis, so a compromised worker
  could forge verdicts for queued jobs; rotate the token after a suspected escape.
- Packages travel through the API once per worker (then cached by hash).
