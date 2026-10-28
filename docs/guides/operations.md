# Operations

## Health

| Endpoint | Meaning |
| --- | --- |
| `GET /healthz` | The process is up |
| `GET /readyz` | Postgres answers (503 otherwise); Redis is reported, and its failure shows as `degraded` |
| `GET /api/v1/system` (staff) | Version, backends, whether Redis answers, the judge queue (`waiting`, `in_progress`, `workers`), languages, counts |
| `GET /api/v1/judge/queue` (staff) | The queue alone |
| `/metrics` | Prometheus: HTTP metrics on the API; `codejudge_judge_jobs_total` by verdict and `codejudge_judge_seconds` on each judge (`METRICS_PORT`) |

## Scaling judges

A judge worker judges one submission at a time. Throughput is roughly the number of workers
divided by the average judging time (compile plus all tests). Signs you need more:
`waiting` stays above zero, or people wait for verdicts during a contest.

- Locally: `CJ_JUDGES=4 make up` (each worker takes about one core and up to 3 GB).
- On AWS: raise the judge service's desired count and the Auto Scaling group's size.

Before a contest, scale up in advance: a contest's last ten minutes bring the most
submissions.

## When a judge reports internal errors

`IE` means the judge failed, not the program. Look at the judge's logs
(`make logs SERVICE=judge`):

| Log says | Cause | Fix |
| --- | --- | --- |
| `Couldn't launch the child process` | The sandbox could not start: the container is missing the judge seccomp profile, or the kernel forbids user namespaces | Run with `seccomp=infra/docker/judge-seccomp.json` (Compose does); on hosts with `kernel.unprivileged_userns_clone=0` enable it |
| `package checksum mismatch` | The object store returned a different file | Check storage; re-upload the problem's tests |
| `the problem's checker does not compile` | A broken custom checker | Fix it in the problem editor |
| `the judge gave up after 3 attempts` | The job crashed three workers | Check the worker logs for the first failure |

After fixing the cause, rejudge the affected submissions (**Submissions**, select, **Rejudge**).

## After fixing a wrong test

1. Fix the tests (a new version is created).
2. Judge the references again; the problem shows whether they pass.
3. **Rejudge all** on the problem: every submission is judged on the current tests;
   scoreboards, gradebooks and analytics follow.

## Backups

Postgres holds everything except test packages, which are in object storage by hash.

- Locally: `docker compose -f deploy/compose/compose.yaml exec postgres pg_dump -U codejudge codejudge > backup.sql`,
  and copy the `objects` volume (or the Floci bucket).
- On AWS: RDS automated backups and snapshots; the objects bucket is versioned.

To restore, load the dump into an empty database, restore the bucket, then start the API
(migrations run on start in Compose; on AWS run `make aws-migrate`).

## Rotating secrets

| Secret | Effect of rotating |
| --- | --- |
| `SESSION_SECRET` | Everyone is signed out |
| `INVITE_TOKEN_PEPPER` | Every outstanding invitation link stops working: resend them |
| `JUDGE_TOKEN` | Update the API and every judge together; do it after any suspected sandbox escape |
| `LOCAL_MASTER_KEY` | The sealed AI key can no longer be opened: enter it again in Settings |

## Purging

Runs on samples or custom input are deleted after a day by the background worker. Other
submissions are kept: grades and contest results depend on them.
