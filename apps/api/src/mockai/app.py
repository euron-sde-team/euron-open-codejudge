"""A stand-in for an OpenAI-compatible LLM, for the demo and the tests (no key, no network).

``POST /v1/chat/completions`` answers with a short, deterministic hint built from the
request, so tests can check what the hint service sent. ``GET /stats`` counts requests:
the AI-off acceptance test reads it to prove that no request was ever made.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="CodeJudge mock AI", docs_url=None, redoc_url=None, openapi_url=None)
STATE: dict[str, Any] = {"requests": 0, "last": None, "fail": False}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stats")
async def stats() -> dict[str, Any]:
    return {"requests": STATE["requests"], "last": STATE["last"]}


@app.post("/admin/reset")
async def reset(request: Request) -> dict[str, str]:
    body = await request.json() if request.headers.get("content-length") not in (None, "0") else {}
    STATE.update(requests=0, last=None, fail=bool(body.get("fail", False)))
    return {"status": "reset"}


@app.post("/v1/chat/completions", response_model=None)
async def chat(request: Request) -> dict[str, Any] | JSONResponse:
    body = await request.json()
    STATE["requests"] += 1
    STATE["last"] = body
    if STATE["fail"]:
        return JSONResponse({"error": {"message": "mock failure"}}, status_code=503)
    messages = body.get("messages") or []
    question = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""
    )
    words = len(str(question).split())
    hint = (
        "Look at the edge cases first: what happens with the smallest and the largest input? "
        "Check how your loop handles them, and whether an intermediate value can overflow. "
        f"(mock hint for a {words}-word question)"
    )
    return {
        "id": f"mock-{STATE['requests']}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "mock"),
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": hint}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": words, "completion_tokens": 40, "total_tokens": words + 40},
    }
