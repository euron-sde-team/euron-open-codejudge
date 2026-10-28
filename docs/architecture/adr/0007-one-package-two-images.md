# ADR-0007: One Python package, two images

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

The API and the judge share the job contract, the language registry and the checker
logic. Two packages would mean publishing one to the other or copying files.

## Decision

One package (`apps/api`, import name `codejudge`) holds the API, the background worker, the
judge worker and the CLI. Two images are built from it: `server.Dockerfile` (Python slim,
for the API, background worker, CLI and mock AI) and `judge.Dockerfile` (Debian with nsjail
built from a pinned tag and the four toolchains). The judge image installs the worker's
virtualenv in `/opt`, which no sandbox mounts, on the same system Python that submissions
use.

## Consequences

**Good**
- One contract, imported by both sides; no version skew.
- The judge image does not carry anything to a sandbox: `/opt` is invisible to programs.

**Bad / caveats**
- The judge image carries API dependencies it never imports (unused, never mounted into a
  sandbox).
