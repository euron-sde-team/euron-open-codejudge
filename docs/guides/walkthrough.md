# Code walkthrough

A guided read of the code, in the order a submission travels.

1. **The contract**: `apps/api/src/codejudge/core/contract.py`. `JudgeJob`, `JudgeResult`,
   the verdicts and `overall()`. Everything else follows from these.
2. **Accepting a submission**: `submissions/router.py` `create_submission` calls
   `submissions/service.py` `submit`: language and size checks, `admit` (the context
   policy from `core/contexts.py`), the rate limit, then the row and `queue.enqueue`.
3. **The queue**: `core/queue.py`. `XADD` to `judge:jobs`; `publish` and `listen` for the
   live events.
4. **The worker loop**: `judge/worker.py`. `next_message` (reclaim, then read), `process`
   (attempts, the heartbeat thread that renews the lease, judging, posting, acknowledging).
5. **Judging**: `judge/runner.py` `Judge.judge`. Compile, fetch the package
   (`judge/packages.py`), run each test, `classify`, `_check`, score by group.
6. **One sandbox run**: `judge/sandbox.py` `Sandbox.command` and `Sandbox.run`. Read it with
   [sandbox.md](../architecture/sandbox.md) open.
7. **Comparing**: `judge/checkers.py`. Streaming token comparison, floats, exact lines, and
   the custom checker exit codes.
8. **Ingesting**: back in `submissions/service.py`, `ingest`: the row lock, the current-job
   check, counters, listeners, the `done` event.
9. **Listeners**: `contests/service.py` (the scoreboard version), `analytics/service.py`
   (`record`, the bucket recount).
10. **Problems**: `problems/service.py` (versions, the publish gate, import and export) and
    `problems/packages.py` (the Kattis format).

Then the contexts, each a policy plus its own pages: `contests/` (with `scoring.py`, pure
functions), `classrooms/`, `assessments/` (with the candidate resolver), and the side
features `plagiarism/`, `analytics/`, `hints/`, `org/`.

The web app follows the same domains under `apps/web/src/features/`. Start with the problem
page: the statement, the editor and the live verdict.

Tests mirror the code: `tests/unit/<domain>/`, `tests/integration/test_<domain>.py`, and
`tests/judge/` for the sandbox ([testing.md](testing.md)).
