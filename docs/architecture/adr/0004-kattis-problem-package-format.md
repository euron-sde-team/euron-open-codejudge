# ADR-0004: The Kattis problem package format

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

Problems are the most valuable thing a judge holds, and the most expensive to make. A
private format locks them in; teachers and contest organisers already have problems in
DOMjudge and Kattis.

## Decision

Store each test version as a zip in the Kattis layout (`problem.yaml`,
`problem_statement/problem.md`, `data/sample`, `data/secret` with groups and
`test_group.yaml`, `output_validators`, `submissions/accepted`), read it on import with the
common variants other tools write, and export the same layout. Builds are deterministic, so
identical tests hash identically.

## Consequences

**Good**
- Problems move between CodeJudge, DOMjudge and Kattis tooling; exports are plain zips.
- The judge reads the format directly; there is no conversion step.

**Bad / caveats**
- 0.1.0 reads a subset: interactive problems, input validators and per-group limits are not
  supported ([problem-format.md](../problem-format.md)).
