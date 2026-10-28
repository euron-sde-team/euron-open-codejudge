# Architecture decision records

Decisions a newcomer would question, with the context and the alternatives.

| ADR | Decision |
| --- | --- |
| [0001](0001-unprivileged-nsjail-sandbox.md) | Sandbox with nsjail in an unprivileged container, never a privileged one |
| [0002](0002-rlimits-not-cgroups.md) | Enforce limits with rlimits and one sandbox per worker, not cgroups |
| [0003](0003-redis-streams-job-queue.md) | A Redis Stream with a consumer group and leases as the judge queue |
| [0004](0004-kattis-problem-package-format.md) | Store, import and export problems in the Kattis package format |
| [0005](0005-judges-hold-no-database-or-storage-credentials.md) | Judge workers hold no database or storage credentials |
| [0006](0006-mit-licence.md) | MIT licence, although the brief suggested Apache 2.0 or AGPLv3 |
| [0007](0007-one-package-two-images.md) | One Python package for the API and the judge, two images |
| [0008](0008-no-proc-in-the-sandbox.md) | No `/proc` inside the sandbox |
