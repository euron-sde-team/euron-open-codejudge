# Contributing

Thanks for helping improve Euron Open CodeJudge. This guide covers the workflow, the bar a
change has to clear, and the conventions the codebase follows.

## Ground rules

- **Open an issue first** for anything larger than a bug fix or a docs tweak, so we can
  agree on the approach before you invest time.
- **One concern per pull request.** A refactor and a feature are two PRs.
- **Security issues go through private reporting**, never a public issue. That includes
  any way out of the judge sandbox. See [SECURITY.md](SECURITY.md).
- By contributing you agree your work is released under the [MIT License](LICENSE).

## Development setup

Requirements: Docker, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 and
pnpm 9 (`corepack enable`).

```bash
make up          # Postgres, Redis, Mailpit, Floci (provisioned by Terraform), api, worker, judges, web
make demo        # users, real problems judged for real, contests, a class, an interview, history
make test        # unit tests (API and web)
```

The judge runs only inside its image (it needs nsjail and the toolchains): use
`make test-judge` for anything under `apps/api/src/codejudge/judge/`.
[docs/guides/quickstart-local.md](docs/guides/quickstart-local.md) walks through the local
stack in detail.

## Before you open a pull request

Each of these must pass:

```bash
make lint typecheck test
make test-integration                  # the API against real Postgres and Redis
make test-judge                        # when you touched the judge, a language or the image
make e2e                               # when you touched a web flow or infrastructure
make tf-validate tf-lint tf-security   # when you touched infra/terraform
make tf-aws-on-floci                   # same: apply and destroy aws-dev against Floci
make openapi                           # when you changed an endpoint
make sanitize                          # no credentials, account ids, resource ids or dashes
```

## Conventions

**Package by domain.** `apps/api/src/codejudge/<domain>/` owns its `router.py` (HTTP only),
`schemas.py` (the public contract), `service.py` (rules) and `models.py`. Dependencies point
inward: router, service, data. A domain calls another domain's service, never its tables.

**Contexts plug in, the judge path stays put.** A new place where people submit (a new kind
of event) registers a policy and listeners in `core/contexts.py`; it does not edit
`submissions/`. Periodic work registers with `core/tasks.py`.

**The judge holds nothing it does not need.** Judge workers get the judge token and the
Redis URL, nothing else. A change that gives them database, storage or session secrets will
not be merged. The contract between the API and the judge is `core/contract.py`.

**Hidden tests never leave the judge.** No response to a non-staff user, no hint prompt, no
log line may carry hidden test input or answers. Per-test output exists only for samples.

**Verdicts come from measurements.** The sandbox measures CPU time and memory with `wait4`;
verdicts are decided from those in a fixed order (see
[docs/architecture/sandbox.md](docs/architecture/sandbox.md)). Do not add guesses.

**The sandbox stays unprivileged.** Never add a capability, `privileged: true`, or a mount of
the worker's files into a sandbox. Changes to the seccomp profile, the kafel policy or the
mounts need a hostile test that proves the change.

**Configuration is validated.** A new setting goes in `core/config.py`, is documented in
[docs/guides/configuration.md](docs/guides/configuration.md) in the same PR, and
security-relevant ones are enforced by `guard()` at boot.

**Database changes are new migrations.** Change the models, then autogenerate a revision
with `uv run codejudge revision -m "what changed"` against a local database and review it.
Never edit an applied one. Indexes for every new filter the API exposes belong in the same
revision.

**Comments explain why.** The code says what it does. Comments are for the constraint, the
incident, or the trade-off that made it this way.

**Style.** ruff and mypy `--strict` for Python; ESLint and TypeScript strict for the web.
No em dashes or en dashes anywhere (the sanitization check enforces it).

## Adding a language

Install the toolchain in `infra/docker/judge.Dockerfile`, add an entry to
`apps/api/src/codejudge/judge/languages.yaml`, and add the verdict fixtures for it under
`apps/api/tests/judge/programs/<language>/` (accepted, wrong answer, time limit, memory
limit, runtime error, compilation error, output limit). `make test-judge` must pass.

## Commit messages

Imperative mood with an optional scope: `judge: classify output at the limit before time`,
`web: show the frozen banner on the scoreboard`. Explain the why in the body when it is not
obvious.

## Architecture decisions

Significant decisions are recorded in [docs/architecture/adr/](docs/architecture/adr/).
If your change reverses or extends one, add a new ADR rather than editing the old one.
