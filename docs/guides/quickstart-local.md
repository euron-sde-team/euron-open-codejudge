# Quickstart (local)

Everything runs in Docker on one machine. No AWS account, no API keys.

## Prerequisites

- Docker with Compose v2 (Docker Desktop or Docker Engine on Linux)
- `make`, `bash`, `openssl`
- About 3 GB of disk for the images (the judge image carries GCC, OpenJDK 21, Node.js and
  Python)

## Start

```bash
git clone https://github.com/euron-sde-team/euron-open-codejudge.git
cd euron-open-codejudge
make up      # Postgres, Redis, Mailpit, Floci (provisioned by Terraform), api, worker, judges, web
make demo    # users, 12 problems judged for real, contests, a class, an interview, a month of history
```

`make up` generates `deploy/compose/.env` with random local secrets the first time, builds
the images and waits until everything is healthy. The first build of the judge image
compiles nsjail and downloads the toolchains; on a slow route to Debian's mirrors set
`CJ_APT_MIRROR` (see [troubleshooting](troubleshooting.md)).

`make demo` prints the sign-in details. Open http://localhost:4710.

| Who | Email | Sees |
| --- | --- | --- |
| Admin | `admin@codejudge.local` | Everything, settings, users, audit |
| Teacher | `priya.raman@codejudge.local` | The class CS201, problem editor, plagiarism, analytics |
| Interviewer | `daniel.okafor@codejudge.local` | The coding screen and its candidate report |
| Student | `aarav.mehta@students.example` | Problems, contests, the class, their progress |

All demo accounts share the printed password. Candidate invitation emails are in Mailpit at
http://localhost:4725.

## Five minutes

1. Sign in as the admin. **Problems** lists the demo set; open **Sum of Two**, pick a
   language, press **Run** to try the samples, then **Submit**. The verdict arrives live.
2. Submit something wrong (print `a - b`) and look at the per-test table: the sample shows
   your output and the checker's message; hidden tests show only their verdict.
3. **Manage problems**, **New problem**: give it a slug and a title, add a sample and a
   hidden test in the **Tests** tab, add a reference solution, press **Judge references**,
   then **Publish** once it says it can.
4. Open **Contests**, **Weekly Round 42**: the live IOI scoreboard of the demo.
5. Sign in as the teacher and open **Classes**, **CS201**, **Week 3**: the gradebook, with
   the late penalty applied.

## Stop

```bash
make down    # stops the stack and deletes its data
```

## Next

- [Writing problems](writing-problems.md)
- [Configuration](configuration.md)
- [Code walkthrough](walkthrough.md)
