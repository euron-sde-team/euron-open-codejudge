# ADR-0008: No /proc in the sandbox

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

Docker overmounts parts of a container's `/proc`. The kernel refuses to mount a new procfs
inside a user namespace when the existing `/proc` has overmounts, so an unprivileged
container cannot give a sandbox its own `/proc`. Found while running the judge suite: every
compilation that asked for `/proc` failed to launch.

## Decision

Sandboxes never mount `/proc` (`--disable_proc`). The one thing that needed it is the JDK:
glibc resolves `$ORIGIN` in `RPATH` through `/proc/self/exe`, so the launcher cannot find
`libjli.so`. Java commands set `LD_LIBRARY_PATH=/usr/lib/jvm/java-21/lib`, and the image
links `/usr/lib/jvm/java-21` to the architecture's JDK. A language entry may carry `env`
for such cases.

## Consequences

**Good**
- Works unprivileged; programs see less of the system.

**Bad / caveats**
- Programs that read `/proc` (their own memory maps, CPU count) do not work; none of the
  four languages needs it for normal programs.
