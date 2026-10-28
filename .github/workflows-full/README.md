# Full CI pipeline (opt-in)

These workflows are the complete quality pipeline for Euron Open CodeJudge. They are kept
here, outside `.github/workflows/`, so they do **not** run on the upstream repository.
Only the fast [`checks`](../workflows/checks.yml) workflow (lint, typecheck, unit tests,
web build) runs there.

| Workflow | What it runs |
| --- | --- |
| [`ci.yml`](ci.yml) | Sanitization scan, OpenAPI drift, and the integration suite on Postgres 16 and Redis 7: the real API driven through the real judge job stream by a fake judge, with an 85% coverage floor |
| [`judge.yml`](judge.yml) | The judge in its real image: verdicts in Python, C++, Java and JavaScript and the hostile-code suite, with the production hardening (no capabilities, no new privileges, the judge seccomp profile, read-only root, no network) |
| [`security.yml`](security.yml) | gitleaks over full history, CodeQL (Python and TypeScript), pip-audit, pnpm audit |
| [`terraform.yml`](terraform.yml) | `terraform fmt` and `validate` for every environment, tflint, checkov, and the full `aws-dev` environment applied and destroyed against Floci |
| [`docker.yml`](docker.yml) | Multi-arch image builds for the api, judge and web images |
| [`e2e.yml`](e2e.yml) | The full stack on the local AWS emulator: the integration suite under every key and storage backend, the Playwright browser tests and the Puppeteer QA sweep |

To enable them in your fork, move them into `.github/workflows/`:

```bash
git mv .github/workflows-full/*.yml .github/workflows/
```

Every gate is also runnable locally:
`make lint typecheck test test-integration test-judge test-matrix e2e qa tf-validate tf-lint tf-security tf-aws-on-floci sanitize`.
