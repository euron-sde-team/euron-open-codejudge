"""The language registry (``languages.yaml``): how each language compiles and runs.

The API reads it to list languages and their editor templates; the judge reads it to build
commands. Both read the same file, so a language the API offers is one the judge runs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_FILE = Path(__file__).with_name("languages.yaml")


class Language(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    source: str = Field(pattern=r"^[A-Za-z0-9_.]{1,64}$")
    compile: list[str] = Field(default_factory=list)
    exe: str | None = None
    run: list[str]
    memory_mode: Literal["address", "rss"] = "address"
    memory_overhead_mb: int = Field(0, ge=0, le=1024)
    time_factor: float = Field(1.0, gt=0, le=10)
    # Processes and threads the program may have at once (the JVM needs a few dozen).
    threads: int = Field(1, ge=1, le=256)
    monaco: str = "plaintext"
    template: str = ""

    def command(self, parts: list[str], *, mem_mb: int, stack_mb: int) -> list[str]:
        values = {
            "src": self.source,
            "exe": self.exe or "",
            "mem": str(mem_mb),
            "stack": str(stack_mb),
        }
        return [p.format(**values) for p in parts]

    def time_limit_ms(self, problem_ms: int) -> int:
        return round(problem_ms * self.time_factor)


def load(path: str | Path | None = None) -> dict[str, Language]:
    raw = yaml.safe_load(Path(path or DEFAULT_FILE).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("languages file must map language ids to their settings")
    return {lid: Language(id=lid, **spec) for lid, spec in raw.items()}


@lru_cache
def registry(path: str | None = None) -> dict[str, Language]:
    return load(path)
