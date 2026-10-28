# ADR-0006: MIT licence

- **Status:** Accepted
- **Date:** 2026-10-28

## Context

The project brief suggested Apache 2.0 for broad adoption, or AGPLv3 to make network
operators share changes. Every project in the Euron open-source programme is MIT licensed,
so that schools, companies and individuals can adopt and adapt it with the fewest
conditions.

## Decision

MIT, copyright ENGAGESPHERE TECHNOLOGY PRIVATE LIMITED and the Euron Open CodeJudge
contributors. Third-party components keep their own licences: nsjail (Apache 2.0) and the
toolchains (GCC, OpenJDK, Node.js, CPython) are installed in the judge image as separate
programs, not linked into CodeJudge's code.

## Consequences

**Good**
- The simplest terms to adopt, the same as the rest of the programme.

**Bad / caveats**
- Someone can run a modified CodeJudge as a service without sharing the changes (what AGPL
  would prevent). That is accepted.
