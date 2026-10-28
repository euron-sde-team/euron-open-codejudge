"""Runtime configuration, validated once at boot.

Every setting comes from the environment. The control plane (api, background worker, CLI)
reads ``Settings``; the judge worker reads ``JudgeSettings``, which deliberately holds no
database or storage credentials: it reaches only the job stream and the API's internal
endpoints. Security-relevant settings are checked by ``guard()`` so a misconfigured
production deployment refuses to start instead of running with demo secrets.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

INSECURE_SECRETS = {"", "change-me", "replace-with-output-of-make-env", "dev", "secret"}


def _split(v: object) -> object:
    if isinstance(v, str):
        return [item.strip() for item in v.split(",") if item.strip()]
    return v


def _insecure(value: str) -> bool:
    return value in INSECURE_SECRETS or "not-for-production" in value or len(value) < 32


class _Base(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"


class Settings(_Base):
    """The control plane: API, background worker and CLI."""

    cloud: Literal["local", "floci", "aws"] = Field("local", alias="CODEJUDGE_CLOUD")

    database_url: str = "postgresql+asyncpg://codejudge:codejudge@localhost:4742/codejudge"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    # The judge job stream lives in Redis, so the judge needs it. Caches and rate limits
    # use it too; with it empty they run in process and judging is unavailable.
    redis_url: str = ""
    memory_cache_max_bytes: int = Field(64_000_000, ge=1_000_000)

    session_secret: str = "dev-session-secret-not-for-production"  # noqa: S105 dev default, refused in production by guard()
    invite_token_pepper: str = "dev-invite-pepper-not-for-production"  # noqa: S105 refused in production
    session_ttl_hours: int = 12
    cookie_secure: bool = False
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:4710"]
    )
    # Where people open the app; used in invitation emails.
    public_url: str = "http://localhost:4710"

    # Secrets stored in the database (the AI provider key) are sealed first.
    key_mode: Literal["local", "kms"] = "local"
    local_master_key: str = "dev-local-master-key-not-for-production"
    kms_key_id: str = "alias/codejudge-local"

    aws_region: str = "us-east-1"
    aws_endpoint_url: str | None = None
    s3_force_path_style: bool = False
    # Test data packages (by content hash), exports and backups. Rows keep only the key.
    objects_bucket: str = "codejudge-local-objects"
    storage: Literal["local", "s3"] = "local"
    local_storage_dir: str = "./.data/objects"

    # Mail for invitations: "log" prints them (development), "smtp" (Mailpit locally,
    # any SMTP relay), "ses" (AWS).
    mail_backend: Literal["log", "smtp", "ses"] = "log"
    mail_from: str = "CodeJudge <no-reply@codejudge.local>"
    smtp_host: str = "localhost"
    smtp_port: int = Field(4726, ge=1, le=65535)

    # Shared with the judge workers: authenticates their calls to /internal.
    judge_token: str = "dev-judge-token-not-for-production"  # noqa: S105 refused in production
    # Upper bounds a problem setter can choose (on create, edit and import).
    max_time_limit_ms: int = Field(10_000, ge=100, le=60_000)
    max_memory_limit_mb: int = Field(1024, ge=16, le=8192)
    max_source_bytes: int = Field(128_000, ge=1_000, le=2_000_000)
    max_package_bytes: int = Field(256_000_000, ge=1_000_000)

    # Optional AI hints. Off unless an admin turns them on and sets an endpoint.
    ai_allow_private_endpoints: bool = True

    submit_rpm: int = 12
    max_body_bytes: int = 2_000_000
    max_internal_body_bytes: int = 64_000_000
    worker_poll_interval_s: float = 30.0
    worker_metrics_port: int = Field(9464, ge=0, le=65535)
    otel_enabled: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        return _split(v)

    @property
    def cache_backend(self) -> Literal["redis", "memory"]:
        return "redis" if self.redis_url else "memory"

    def guard(self) -> None:
        """Refuse to boot in production with demo secrets or unsafe options."""
        if self.environment != "production":
            return
        names = ("session_secret", "invite_token_pepper", "judge_token")
        problems: list[str] = [
            f"{name.upper()} must be a random value of at least 32 chars"
            for name in names
            if _insecure(getattr(self, name))
        ]
        if self.key_mode == "local" and _insecure(self.local_master_key):
            problems.append("LOCAL_MASTER_KEY must be set (or use KEY_MODE=kms)")
        secrets = [getattr(self, n) for n in names]
        if len(set(secrets)) != len(secrets):
            problems.append("SESSION_SECRET, INVITE_TOKEN_PEPPER and JUDGE_TOKEN must all differ")
        if not self.redis_url:
            problems.append("REDIS_URL must be set: the judge queue needs it")
        if self.cloud == "aws" and self.aws_endpoint_url:
            problems.append("AWS_ENDPOINT_URL must be unset when CODEJUDGE_CLOUD=aws")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true in production")
        if self.mail_backend == "log":
            problems.append("MAIL_BACKEND must be smtp or ses in production (invitations)")
        if problems:
            raise RuntimeError("unsafe production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.guard()
    return settings


class JudgeSettings(_Base):
    """A judge worker. No database, storage or session secrets: a compromised worker can
    reach only the job stream and the API's token-protected internal endpoints."""

    api_internal_url: str = "http://localhost:4730"
    judge_token: str = "dev-judge-token-not-for-production"  # noqa: S105 refused in production
    redis_url: str = "redis://localhost:4779/0"
    worker_name: str = ""
    # Test data cached on local disk by content hash, verified on every load.
    cache_dir: str = "/var/cache/codejudge"
    cache_max_bytes: int = Field(2_000_000_000, ge=10_000_000)
    # Scratch space for one run (compile output, the box). A tmpfs in the container.
    work_dir: str = "/tmp/judge"  # noqa: S108 a private tmpfs inside the worker container
    nsjail_path: str = "/usr/local/bin/nsjail"
    languages_file: str = ""
    # Compilation limits, separate from the problem's run limits.
    compile_time_limit_s: float = Field(20.0, gt=0, le=120)
    compile_memory_mb: int = Field(1024, ge=64, le=8192)
    # Output beyond this is truncated and the run is Output Limit Exceeded.
    max_output_bytes: int = Field(64_000_000, ge=1024)
    # Wall clock allowance on top of the CPU limit (a program sleeping forever is TLE).
    wall_factor: float = Field(2.0, ge=1.0, le=10.0)
    wall_extra_s: float = Field(1.0, ge=0.0, le=30.0)
    heartbeat_s: float = Field(15.0, ge=1.0, le=300.0)
    # A job whose worker stops heart-beating for this long is claimed by another worker
    # (the first one died); at least four heartbeats, so a slow beat is never mistaken.
    lease_s: float = Field(60.0, ge=10, le=3600)
    # Deliveries before a job is reported as an internal error instead of retried again.
    max_attempts: int = Field(3, ge=1, le=10)
    metrics_port: int = Field(9465, ge=0, le=65535)

    def guard(self) -> None:
        if self.environment == "production" and _insecure(self.judge_token):
            raise RuntimeError(
                "unsafe production configuration: JUDGE_TOKEN must be a random value of "
                "at least 32 chars"
            )


@lru_cache
def get_judge_settings() -> JudgeSettings:
    settings = JudgeSettings()
    settings.guard()
    return settings
