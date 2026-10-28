## What and why

<!-- One paragraph: the problem, and how this change solves it. Link the issue. -->

## How it was verified

- [ ] `make lint typecheck test`
- [ ] `make test-integration` (if the API, a cache or database code changed)
- [ ] `make test-judge` (if the judge, the sandbox, a language or the judge image changed)
- [ ] `make e2e` (if a user flow or infrastructure changed)
- [ ] `make tf-validate tf-lint tf-security tf-aws-on-floci` (if Terraform changed)

## Checklist

- [ ] Docs updated (README, `docs/`, configuration reference) for any behavior or config change
- [ ] New Alembic revision instead of editing an applied one
- [ ] Hidden test data still never reaches a contestant, a candidate or the sandboxed program
- [ ] The judge still runs without privileges (no new capability, no privileged mode, no wider seccomp profile)
- [ ] No new place where submissions are sent outside the deployment (AI hints stay opt-in)
- [ ] `make openapi` run if the API changed
- [ ] No secrets, account ids, real hostnames or em/en dashes (`make sanitize` is clean)
- [ ] Security-relevant change? Described the threat and mitigation above
