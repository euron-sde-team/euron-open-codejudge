# Configuration

Every setting is an environment variable, read once at start and validated
(`apps/api/src/codejudge/core/config.py`). In production (`ENVIRONMENT=production`) the API
refuses to start with demo secrets, equal secrets, no Redis, `COOKIE_SECURE=false`,
`MAIL_BACKEND=log`, or an `AWS_ENDPOINT_URL` with `CODEJUDGE_CLOUD=aws`.

## API and background worker (`Settings`)

### Runtime and database

| Variable | Default | Meaning |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `development`, `test` or `production` (production enables the guards above) |
| `LOG_LEVEL` | `INFO` | Log level |
| `CODEJUDGE_CLOUD` | `local` | `local`, `floci` or `aws`: where AWS calls go (informational, plus the guard above) |
| `DATABASE_URL` | `postgresql+asyncpg://codejudge:codejudge@localhost:4742/codejudge` | Postgres (asyncpg driver) |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | `10`, `20` | Connection pool per process |
| `REDIS_URL` | empty | The judge job stream, live verdict events, rate limits and the scoreboard cache. Required for judging: without it submissions fail with "Judging needs Redis" (production refuses to start) |
| `MEMORY_CACHE_MAX_BYTES` | `64000000` | Size of the in-process cache used when Redis is not set |

### Sessions and links

| Variable | Default | Meaning |
| --- | --- | --- |
| `SESSION_SECRET` | dev value | Signs session tokens. At least 32 random characters in production |
| `INVITE_TOKEN_PEPPER` | dev value | HMAC key for interview invitation tokens (only the HMAC is stored) |
| `SESSION_TTL_HOURS` | `12` | Session lifetime |
| `COOKIE_SECURE` | `false` | Secure flag on the session cookie; must be true in production |
| `CORS_ORIGINS` | `http://localhost:4710` | Comma separated origins allowed to call the API from a browser |
| `PUBLIC_URL` | `http://localhost:4710` | Where people open the app; used in invitation links (`PUBLIC_URL/take/<token>`) |

### Secrets at rest and storage

| Variable | Default | Meaning |
| --- | --- | --- |
| `KEY_MODE` | `local` | `local` seals the AI provider key with AES-GCM and `LOCAL_MASTER_KEY`; `kms` uses KMS |
| `LOCAL_MASTER_KEY` | dev value | The local sealing key (required in production when `KEY_MODE=local`) |
| `KMS_KEY_ID` | `alias/codejudge-local` | The KMS key for `KEY_MODE=kms` |
| `AWS_REGION` | `us-east-1` | AWS region |
| `AWS_ENDPOINT_URL` | unset | Set to the emulator (`http://floci:4566`) locally; unset on AWS |
| `S3_FORCE_PATH_STYLE` | `false` | Path-style S3 URLs (needed for the emulator) |
| `STORAGE` | `local` | `local` (disk under `LOCAL_STORAGE_DIR`) or `s3` (`OBJECTS_BUCKET`) for test packages |
| `OBJECTS_BUCKET` | `codejudge-local-objects` | The bucket |
| `LOCAL_STORAGE_DIR` | `./.data/objects` | The directory for `STORAGE=local` |

### Mail

| Variable | Default | Meaning |
| --- | --- | --- |
| `MAIL_BACKEND` | `log` | `log` (nothing leaves the process), `smtp` (Mailpit locally, any relay) or `ses` |
| `MAIL_FROM` | `CodeJudge <no-reply@codejudge.local>` | Sender |
| `SMTP_HOST`, `SMTP_PORT` | `localhost`, `4726` | For `MAIL_BACKEND=smtp` (Compose points it at `mailpit:1025`) |

### Judging and limits

| Variable | Default | Meaning |
| --- | --- | --- |
| `JUDGE_TOKEN` | dev value | Shared with the judge workers; authenticates `/internal/judge/*`. Must differ from the other secrets |
| `MAX_TIME_LIMIT_MS`, `MAX_MEMORY_LIMIT_MB` | `10000`, `1024` | The highest limits a problem may set: creating or editing one above them is refused, imported packages are lowered with a warning. Size the judge's memory to the memory maximum |
| `MAX_SOURCE_BYTES` | `128000` | Longest submission |
| `MAX_PACKAGE_BYTES` | `256000000` | Largest test package (upload and built) |
| `SUBMIT_RPM` | `12` | Submissions and runs per person per minute |
| `MAX_BODY_BYTES` | `2000000` | General request body limit (staff package uploads use `MAX_PACKAGE_BYTES`) |
| `MAX_INTERNAL_BODY_BYTES` | `64000000` | Body limit on `/internal/*` (judge results) |

### AI hints, workers, telemetry

| Variable | Default | Meaning |
| --- | --- | --- |
| `AI_ALLOW_PRIVATE_ENDPOINTS` | `true` | Allow the AI base URL to be a private address (a local model). Metadata addresses are always refused. The rest of the AI settings live in the database (admin Settings page) |
| `WORKER_POLL_INTERVAL_S` | `30` | Background worker tick when idle |
| `WORKER_METRICS_PORT` | `9464` | Background worker Prometheus port (0 disables) |
| `OTEL_ENABLED` | `false` | OpenTelemetry tracing |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Proxies whose `X-Forwarded-For` is trusted (the VPC CIDR on AWS) |
| `PORT` | `8080` | Listen port in the container |

## Judge worker (`JudgeSettings`)

A judge reads only these. It gets no database, storage or session secret.

| Variable | Default | Meaning |
| --- | --- | --- |
| `API_INTERNAL_URL` | `http://localhost:4730` | The API as the judge reaches it (`http://api:8080` in Compose) |
| `JUDGE_TOKEN` | dev value | Same value as the API's |
| `REDIS_URL` | `redis://localhost:4779/0` | The job stream |
| `WORKER_NAME` | the host name | Consumer name in the stream and in results |
| `CACHE_DIR` | `/var/cache/codejudge` | Test packages by hash |
| `CACHE_MAX_BYTES` | `2000000000` (Compose: `1000000000`) | Package cache budget, least recently used evicted before a new package arrives. Keep it inside the cache tmpfs: tmpfs pages count against the container's memory |
| `WORK_DIR` | `/tmp/judge` | Scratch for one run (needs exec: compiled programs run from it) |
| `NSJAIL_PATH` | `/usr/local/bin/nsjail` | The nsjail binary |
| `LANGUAGES_FILE` | the bundled `languages.yaml` | Your own language registry |
| `COMPILE_TIME_LIMIT_S`, `COMPILE_MEMORY_MB` | `20`, `1024` | Compiler limits |
| `MAX_OUTPUT_BYTES` | `64000000` | Ceiling on any problem's output limit |
| `WALL_FACTOR`, `WALL_EXTRA_S` | `2.0`, `1.0` | Wall clock allowance: CPU limit times the factor plus the extra |
| `HEARTBEAT_S` | `15` | Lease renewal and progress interval |
| `LEASE_S` | `60` | A job whose worker stops renewing for this long is claimed by another (at least four heartbeats) |
| `MAX_ATTEMPTS` | `3` | Deliveries before a job is reported as an internal error |
| `METRICS_PORT` | `9465` | Prometheus port (0 disables) |
| `ENVIRONMENT`, `LOG_LEVEL` | as above | Production refuses a weak `JUDGE_TOKEN` |

## Local stack (`deploy/compose/.env`)

`make env` writes the secrets (`SESSION_SECRET`, `INVITE_TOKEN_PEPPER`, `LOCAL_MASTER_KEY`,
`JUDGE_TOKEN`, `CJ_DEMO_PASSWORD`) once. Optional overrides:

| Variable | Default | Meaning |
| --- | --- | --- |
| `CJ_WEB_PORT` | `4710` | Web app |
| `CJ_API_PORT` | `4730` | API |
| `CJ_MAILPIT_PORT` | `4725` | Mailpit web UI |
| `CJ_MOCK_AI_PORT` | `4750` | The mock language model |
| `CJ_PG_PORT`, `CJ_REDIS_PORT`, `CJ_FLOCI_PORT` | `4742`, `4779`, `4766` | Postgres, Redis, Floci |
| `CJ_JUDGES` | `2` | Judge workers (each judges one submission at a time) |
| `CJ_APT_MIRROR` | empty | A faster Debian mirror for building the judge image, an `http` URL ending in `/debian` that also serves `<url>-security` |
| `CJ_LOG_LEVEL` | `INFO` | Log level for every service |
| `CJ_DEMO_PASSWORD` | random | Password of every demo account |
| `CJ_DEMO_AI_URL` | `http://mock-ai:4750/v1` | Where the demo points AI hints |

## Languages

`apps/api/src/codejudge/judge/languages.yaml` defines each language: file name, compile and
run commands, how memory is limited (`address` or `rss`), a time factor, threads and extra
environment. Point `LANGUAGES_FILE` at your own copy (the API and the judges must read the
same file) and install the toolchain in the judge image. See
[LLD.md](../architecture/LLD.md#languages).
