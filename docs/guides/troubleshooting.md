# Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `make up` fails with "port is already allocated" | Something else uses 4710, 4725, 4730, 4742, 4750, 4766 or 4779 | Set the matching `CJ_*_PORT` in `deploy/compose/.env` ([configuration.md](configuration.md#local-stack-deploycomposeenv)) |
| Compose says "run `make env` first" | `deploy/compose/.env` is missing a secret | `make env` (never overwrites); `make down` after regenerating so the database matches |
| Building the judge image takes very long at `apt-get install` | A slow route to `deb.debian.org` (the default CDN) | Set `CJ_APT_MIRROR` to a faster official mirror that also serves `-security`, for example `CJ_APT_MIRROR=http://ftp.de.debian.org/debian make up`. The default stays the standard mirror |
| Building the judge image stops at `git clone` of nsjail | GitHub unreachable or slow | Retry; the clone is a pinned tag and is cached after the first success |
| Every submission is `IE` with "Couldn't launch the child process" | The judge runs without its seccomp profile, or user namespaces are disabled on the host | Use the Compose service as is; on Linux check `sysctl kernel.unprivileged_userns_clone` (Debian, older Ubuntu) and AppArmor's `kernel.apparmor_restrict_unprivileged_userns` (Ubuntu 24.04+) |
| Submissions stay `queued` | No judge is running, or it cannot reach Redis or the API | `make ps`, `make logs SERVICE=judge`; the system page shows how many workers are connected |
| "Judging needs Redis" | `REDIS_URL` is empty | Set it; the queue lives in Redis |
| Java programs fail with `libjli.so: cannot open shared object file` | A custom languages file without the JDK's `LD_LIBRARY_PATH` | Keep `env: ["LD_LIBRARY_PATH=/usr/lib/jvm/java-21/lib"]` on Java entries ([ADR-0008](../architecture/adr/0008-no-proc-in-the-sandbox.md)) |
| A correct solution gets TLE on a busy laptop | Limits are CPU time, but the wall clock allowance is `WALL_FACTOR` times that | Close what is swapping; raise `WALL_FACTOR` if the machine is shared |
| A problem cannot be published | Its reference solutions have not been judged on the current tests, or got the wrong verdict | The problem editor lists the blockers; press **Judge references** |
| Candidates do not receive invitations locally | Mail goes to Mailpit, not the internet | Open http://localhost:4725 |
| Invitations on AWS go nowhere | SES is still in its sandbox, or DKIM is not set | Add the DKIM records; request production access |
| The AI hint button is missing | AI is off (the default), not allowed in this context, or the cap is reached | Admin **Settings**; contests and assessments never allow hints |
| "The request body is larger than ..." | Over the 2 MB general limit | Upload large tests as a package from the problem editor (staff, signed in) |
