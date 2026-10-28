# ADR-0001: Sandbox with nsjail in an unprivileged container

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

A judge runs code that is hostile by assumption. The usual designs either trust Docker
alone (one container per run, a weak boundary for hostile code and slow to start) or run a
proper sandbox (isolate, nsjail) inside a **privileged** container, because those sandboxes
create cgroups and cgroup v2 in a container needs privilege or delegation. Judge0 does the
latter, and in 2024 three of its vulnerabilities (CVE-2024-28185, CVE-2024-28189,
CVE-2024-29021) became host takeovers precisely because an escape from its inner sandbox
was root in a privileged container.

## Decision

Run each compilation and test in a fresh nsjail sandbox built from user, PID, network,
mount, IPC and UTS namespaces, inside a worker container that has every capability dropped,
`no-new-privileges`, a read-only root and Docker's default seccomp profile extended with
only the namespace calls nsjail needs (`clone, unshare, mount, umount2, pivot_root,
sethostname, setdomainname, setns`). A second, kafel syscall filter makes those calls (and
`ptrace`, `bpf`, `io_uring`, keyrings and more) fail inside the program's sandbox. A
prototype on 2026-10-28 confirmed it works on Docker Desktop's kernel with zero
capabilities; the hostile suite (`make test-judge`) proves it on every run.

## Consequences

**Good**
- An escape from the inner sandbox lands as an unprivileged user in an unprivileged
  container with no network but the API and Redis, holding no database credentials.
- Starting a sandbox costs about 8 ms, not a container start.
- The same image runs under Compose and ECS with the same hardening.

**Bad / caveats**
- The kernel's user namespace code is attack surface; the filter removes common entry
  points but a namespace 0-day remains possible. Public judges should add gVisor, Kata or
  dedicated hosts ([sandbox.md](../sandbox.md)).
- The worker container needs a custom seccomp profile, which Fargate cannot take: judges run
  on an EC2 capacity provider on AWS.
- No cgroups: see [ADR-0002](0002-rlimits-not-cgroups.md).

## Alternatives considered

- **isolate in a privileged container**: precise cgroup accounting, but privileged.
- **A container per run** (Docker or Firecracker via an orchestrator): stronger kernel
  boundary with Firecracker, but heavy to operate and seconds per run.
- **gVisor for every run**: a strong boundary and a good add-on, but not available on
  Docker Desktop by default; documented as the hardening step for public judges.
