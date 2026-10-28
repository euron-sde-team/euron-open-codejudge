# Threat model

The attacks considered, what stops each, and what is left. STRIDE-style; the controls are
described in [security.md](security.md) and [sandbox.md](sandbox.md).

| # | Threat | Actor | Mitigation | Residual risk |
| --- | --- | --- | --- | --- |
| T1 | A submission reads the hidden answers | Student, contestant | Answers never mounted in the program's sandbox; compared outside; no output or checker messages for hidden tests | None known |
| T2 | A submission escapes the sandbox | Anyone who can submit | nsjail per run (user, PID, net, mount namespaces), syscall filter, rlimits; the container itself unprivileged with no network but the API and Redis | Kernel vulnerabilities reachable through namespaces: use gVisor, Kata or dedicated hosts for a public judge |
| T3 | An escaped submission reaches the database, storage or cloud credentials | Attacker after T2 | The worker holds only the judge token and the Redis URL; judge network or security group reaches only the API and Redis; IMDSv2 hop limit 1 and blocked task metadata on AWS; the task role has no permissions | The judge token lets it post results for jobs it can read from Redis: it could forge verdicts for queued jobs. Rotate `JUDGE_TOKEN` after any suspected escape |
| T4 | A submission slows or breaks judging for others | Contestant | One sandbox per worker; CPU time measured per program; rlimits and the container's own limits; the worker survives and judges the next job correctly (tested) | A machine pushed into swap stretches wall clocks; size workers to avoid it |
| T5 | A crafted test package writes outside its directory on the judge | Malicious or careless setter | SHA-256 check, no links, devices, absolute paths or `..`, size and count caps | Setters are staff; a hostile admin is out of scope |
| T6 | A verdict is applied twice, lost, or overwritten by a stale job | Failure, not an attacker | Leases and reclaim; result before acknowledgement; ingest only for the current job and only once, under a row lock | None known |
| T7 | Students read other students' code, or contestants their rivals' | Student | Visibility checked per context; contest code readable by author and staff only, during and after | Staff see everything by design |
| T8 | An interview link is guessed, replayed or shared | Outsider, candidate | Random token stored as HMAC; one assessment, one deadline; resend replaces, revoke kills | A candidate can share their own link during their window; the report shows submissions, not who typed them |
| T9 | Account takeover by password guessing | Outsider | Argon2id, per-IP throttle, per-account lockout in Postgres | Lockout can be used to annoy a known account for 15 minutes |
| T10 | CSRF against a signed-in teacher | Malicious site | Custom header required on cookie mutations; SameSite=Lax cookie; CORS allowlist | None known |
| T11 | Hidden data leaks through the AI provider | Student, provider | Prompts carry samples and the student's own code only, never hidden tests; AI off by default and never in contests or assessments | The student's code goes to the provider when AI is on with a hosted model: tell users, or use a local model |
| T12 | The AI endpoint is used for SSRF | Admin | Metadata addresses refused; private addresses refusable with `AI_ALLOW_PRIVATE_ENDPOINTS=false` | Admins can point it at internal services by design when private endpoints are allowed |
| T13 | Spreadsheet formula injection from names in a CSV | Student | Leading `=`, `+`, `-`, `@` neutralised | None known |
| T14 | The job queue loses work under memory pressure | Failure | Redis with `noeviction` and append-only persistence locally; ElastiCache `noeviction` on AWS | A full Redis refuses new jobs (submitting fails with an error) instead of losing old ones |
| T15 | Denial of service through large uploads | Outsider | Bodies capped before parsing; large bodies only on staff routes with a session; rate limits | Volumetric attacks are for the load balancer and WAF |
