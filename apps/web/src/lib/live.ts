/**
 * Live verdicts: the API streams server-sent events for one submission until its verdict
 * is in. Each `data:` line is JSON such as
 *   {"status": "judging", "progress": "running test 3"}
 *   {"status": "done", "verdict": "WA", "score": 0}
 */

export interface LiveEvent {
  status: "queued" | "judging" | "done";
  verdict?: string;
  progress?: string | null;
  score?: number;
}

/** Parse one event's data; anything malformed is ignored (null), never thrown. */
export function parseLiveEvent(data: string): LiveEvent | null {
  let value: unknown;
  try {
    value = JSON.parse(data);
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null) return null;
  const v = value as Record<string, unknown>;
  if (v.status !== "queued" && v.status !== "judging" && v.status !== "done") return null;
  return {
    status: v.status,
    verdict: typeof v.verdict === "string" ? v.verdict : undefined,
    progress: typeof v.progress === "string" ? v.progress : null,
    score: typeof v.score === "number" ? v.score : undefined,
  };
}

/** Fold events into what the screen shows: the last status wins, a verdict sticks. */
export function applyLiveEvent(current: LiveEvent | null, event: LiveEvent): LiveEvent {
  if (current?.status === "done") return current;
  return {
    status: event.status,
    verdict: event.verdict ?? current?.verdict,
    progress: event.status === "done" ? null : (event.progress ?? current?.progress ?? null),
    score: event.score ?? current?.score,
  };
}

/** What to say while waiting. */
export function progressLabel(event: LiveEvent | null): string {
  if (!event || event.status === "queued") return "Waiting for a judge";
  if (event.status === "judging") {
    const p = event.progress ?? "";
    if (p === "compiling") return "Compiling";
    if (p) return p.charAt(0).toUpperCase() + p.slice(1);
    return "Judging";
  }
  return "Judged";
}
