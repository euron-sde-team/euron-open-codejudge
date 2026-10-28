# ADR-0002: Limits from rlimits and one sandbox per worker, not cgroups

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

cgroups give exact memory ceilings and process counts, but creating them needs a privileged
or cgroup-delegated container ([ADR-0001](0001-unprivileged-nsjail-sandbox.md) rules both
out). rlimits need no privilege but have gaps: `RLIMIT_NPROC` counts per real uid, and
every sandbox maps to the same outside uid; `RLIMIT_AS` limits address space, not resident
memory, which breaks runtimes that reserve far more than they use (the JVM, V8).

## Decision

- Enforce CPU (`RLIMIT_CPU` plus a measured-CPU verdict), address space for C++ and Python,
  processes, file size (output), open files and stack with rlimits; a wall clock limit from
  nsjail.
- For Java and Node, cap the heap with the runtime's own flag and check peak resident memory
  after the run; raise the run's `oom_score_adj` so the kernel kills the submission first.
- Run **one sandbox at a time per worker**, so the per-uid process count is exact, and scale
  throughput with more workers.
- Bound everything with the worker container's own memory, CPU and process limits.

## Consequences

**Good**
- No privilege needed; the same approach DMOJ uses.
- Measurements come from `wait4` and are exact for CPU time and peak memory.

**Bad / caveats**
- A Java or Node program can briefly exceed its memory limit before the verdict is decided
  (bounded by the container limit).
- Throughput per machine is the number of workers on it, not the number of cores.
