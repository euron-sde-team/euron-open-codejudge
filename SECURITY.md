# Security Policy

CodeJudge runs code written by strangers, holds the hidden tests that make its verdicts
mean something, and keeps students' grades and candidates' assessments. We take reports
seriously and respond quickly.

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.x (latest minor) | Yes |
| Older minors | No |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository ("Security" tab, "Report a vulnerability").

Please include:

- the affected component (`apps/api`, the judge worker or its image, `apps/web`,
  `infra/terraform/...`) and version or commit,
- a description of the issue and its impact,
- steps to reproduce, or a proof of concept (for a sandbox escape, the submission source
  and its language),
- any suggested mitigation.

What to expect:

| Stage | Target |
| ----- | ------ |
| Acknowledgement | within 3 business days |
| Initial assessment and severity | within 7 business days |
| Fix or mitigation for critical and high issues | within 30 days |
| Coordinated public disclosure | after a fix is released, credited to you unless you prefer otherwise |

## Scope

In scope: the code in this repository and the infrastructure it provisions with its
default settings. We are especially interested in:

- **any way out of the judge sandbox**: a submission that reaches the network, reads files
  outside its box, writes to the worker, sees another submission or the test data, keeps
  running after its run, or affects another submission's verdict,
- any way for a submission to learn a hidden test's input or answer (through output,
  timing, error messages, checker messages, AI hints or the API),
- a verdict that can be forged, applied twice, or applied to the wrong submission,
- reading or changing other people's submissions, grades, contest results or assessment
  reports; using an invitation link for anything but its own assessment,
- recovering a secret (`SESSION_SECRET`, `INVITE_TOKEN_PEPPER`, `JUDGE_TOKEN`, the master
  key, the AI provider key) from the API, the judge, logs or the database,
- authentication or authorization bypasses, CSRF, and requests from the API reaching an
  address they should not (instance metadata),
- a crafted problem package that writes outside its directory on the judge.

Out of scope:

- **Known limits of namespace sandboxes.** A kernel vulnerability reached through user
  namespaces is in scope if you can show it against the default hardening, but the general
  observation that namespaces are kernel attack surface is documented in
  [docs/architecture/sandbox.md](docs/architecture/sandbox.md).
- **The demo seed.** `make demo` creates well-known demo accounts with the password from
  your local `.env`, on purpose.
- **The mock AI** (`apps/api/src/mockai`), a test fixture never deployed to AWS.
- Staff abusing staff powers (staff can see every submission and every test by design).
- Findings that require a compromised host, compromised AWS account, or leaked deployment
  secrets.
- Denial of service through resource exhaustion of a deployment you operate yourself.

## Hardening checklist for operators

See [docs/architecture/security.md](docs/architecture/security.md#operator-checklist).
