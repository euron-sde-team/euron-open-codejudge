import { describe, expect, it } from "vitest";

import { applyLiveEvent, parseLiveEvent, progressLabel } from "@/lib/live";

describe("live verdict events", () => {
  it("parses the API's event data", () => {
    expect(parseLiveEvent('{"status":"judging","progress":"running test 3"}')).toEqual({
      status: "judging",
      progress: "running test 3",
      verdict: undefined,
      score: undefined,
    });
    expect(parseLiveEvent('{"status":"done","verdict":"WA","score":0}')).toMatchObject({ status: "done", verdict: "WA", score: 0 });
  });
  it("ignores malformed or unknown data instead of throwing", () => {
    expect(parseLiveEvent("not json")).toBeNull();
    expect(parseLiveEvent("42")).toBeNull();
    expect(parseLiveEvent('{"status":"exploded"}')).toBeNull();
  });
  it("keeps the verdict once done, whatever arrives later", () => {
    const done = applyLiveEvent(null, { status: "done", verdict: "AC", score: 100 });
    expect(applyLiveEvent(done, { status: "judging", progress: "compiling" })).toBe(done);
  });
  it("keeps the last progress while judging", () => {
    let state = applyLiveEvent(null, { status: "judging", progress: "compiling" });
    state = applyLiveEvent(state, { status: "judging", progress: "running test 2" });
    expect(state.progress).toBe("running test 2");
    expect(applyLiveEvent(state, { status: "done", verdict: "TLE" })).toMatchObject({ status: "done", verdict: "TLE", progress: null });
  });
  it("says what is happening in plain words", () => {
    expect(progressLabel(null)).toBe("Waiting for a judge");
    expect(progressLabel({ status: "judging", progress: "compiling" })).toBe("Compiling");
    expect(progressLabel({ status: "judging", progress: "running test 4" })).toBe("Running test 4");
    expect(progressLabel({ status: "done", verdict: "AC" })).toBe("Judged");
  });
});
