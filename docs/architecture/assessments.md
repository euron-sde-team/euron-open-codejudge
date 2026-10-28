# Interview assessments

Private, timed assessments for candidates who have no account, with a report for the
interviewer. Code: `assessments/`, `core/mail.py`.

## The flow

1. Staff create an assessment: instructions, problems with points, a duration in minutes,
   and optionally a window (`opens_at`, `closes_at`).
2. They invite candidates by email. Each invitation gets a random token; the database keeps
   only its HMAC-SHA256 (keyed with `INVITE_TOKEN_PEPPER`), and the raw token exists only
   in the email link `PUBLIC_URL/take/<token>`.
3. The candidate opens the link. `POST /api/v1/candidate/session` exchanges the token:
   the first exchange starts the timer, and the deadline is the start plus the duration,
   capped by the closing time.
4. From then on the browser sends the token in the `X-CodeJudge-Candidate` header. It
   resolves to a submitter that can see and submit to that one assessment, before the
   deadline, and nothing else in the install.
5. The candidate submits like anyone else (context `assessment`, the invitation's id) and
   can finish early. After the deadline or finishing, nothing more is accepted.

Resending an invitation issues a new token and kills the old one; revoking stops the link
at once; a periodic task marks invitations past their deadline as expired.

| Status | Meaning |
| --- | --- |
| `invited` | Email sent, link not opened |
| `started` | Timer running |
| `submitted` | The candidate finished |
| `expired` | The deadline or the closing time passed |
| `revoked` | Staff cancelled the link |

## Signals, not proof

The take page records `paste`, `tab_hidden` and `tab_visible` events (rate limited, at most
500 per invitation). The report shows them on the timeline with a note that they are
signals, not proof: a candidate may paste from their own notes or switch tabs to read the
documentation, and a determined one can hide both. They are there to start a
conversation, not to fail someone.

## The report

For each problem the best score; every submission with its code and verdict in time order;
the event timeline; the total. Candidates see sample results only, like students; the
interviewer sees everything.

## Mail

Invitations go out through `MAIL_BACKEND`: `smtp` (Mailpit locally on port 4725 for
reading, any relay in production), `ses` on AWS, or `log` (development and tests: the body
is not logged, because it carries a one-time link).
