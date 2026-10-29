# Testing

Every gate runs locally against Docker; nothing needs a cloud account.

| Command | What it runs | Needs |
| --- | --- | --- |
| `make lint` | ruff (API), ESLint (web) | uv, pnpm |
| `make typecheck` | mypy `--strict` (API), `tsc --noEmit` (web) | uv, pnpm |
| `make test` | API unit tests with an 85% coverage floor; web Vitest | uv, pnpm |
| `make test-integration` | API unit and integration tests against real Postgres and Redis (started if needed) | Docker |
| `make test-judge` | The judge suite inside the judge image, hardened exactly as in production | Docker |
| `make test-matrix` | The integration suite under every storage and key backend (local disk or Floci S3, local sealing or Floci KMS) | Docker |
| `make e2e` | Playwright against the running stack | `make up && make demo` |
| `make qa` | Puppeteer: every page in light and dark at desktop and phone width | `make up && make demo` |
| `make openapi` | Regenerates `docs/api/openapi.yaml` (the drift check compares it with the app) | uv |
| `make tf-validate tf-lint tf-security` | `terraform validate` (3 environments), tflint, checkov | Docker |
| `make tf-aws-on-floci` | The full `aws-dev` environment planned, applied, re-planned and destroyed against a throwaway Floci | Docker |
| `make sanitize` | Credentials, cloud ids and em or en dashes in committed files | bash |

## The judge suite

`apps/api/tests/judge/` runs only where nsjail is installed, so `make test-judge` builds the
`judge-test` target of the judge image and runs it with every capability dropped,
`no-new-privileges`, the judge seccomp profile, a read-only root and an exec tmpfs, mounting
the tests read-only. It covers:

- **Verdicts (AC1)**: accepted, wrong answer, time limit, memory limit, runtime error,
  compilation error and output limit, each in Python, C++, Java and JavaScript; sleeping
  forever; CPU time measured; custom input.
- **Hostile code (AC2)**: network, reading secrets and test data, writing outside the box,
  filling `/tmp`, `unshare`, `ptrace`, `mount`, `chroot`, fork bombs in Python and C++, a
  thread bomb, killing every process, a compiler bomb; then the worker still judges
  correctly.

## The integration harness

`tests/integration/conftest.py` serves the real API over HTTP on a thread, against real
Postgres and Redis, with a **fake judge**: a task that reads the real job stream through the
consumer group and posts results to `/internal/judge/results` with the judge token, exactly
like a worker. Its verdicts come from markers in the source (`#VERDICT:WA`, `#SCORE:40`),
so queueing, ingestion, idempotency, scoreboards and gradebooks are tested quickly and
deterministically. Real compilation and sandboxing are covered by the judge suite and the
browser tests.

Isolation: `TEST_DATABASE_URL` and `TEST_REDIS_URL` choose the database and Redis index; the
suite drops and recreates its database, refuses any database whose name lacks `test`, and
refuses non-local hosts unless `ALLOW_REMOTE_TEST_DB=true`. Two suites with different
databases and Redis indexes can run at once.

## Counts

| Suite | Tests |
| --- | --- |
| API unit | 136 |
| API integration | 90 |
| Judge (in the judge image) | 41 |
| Web unit | 83 |
| Browser end-to-end | 14 |
| Coverage of `apps/api/src` | 90.8% |
