import { describe, expect, it } from "vitest";

import { cellView, freezeBanner, nextLabel } from "@/lib/contest";
import type { ScoreCell } from "@/lib/api/types";

const cell = (over: Partial<ScoreCell>): ScoreCell => ({ label: "A", solved: false, attempts: 0, pending: 0, minute: null, score: 0, first: false, ...over });

describe("ICPC scoreboard cells", () => {
  it("shows solves with wrong tries and the minute", () => {
    expect(cellView("icpc", cell({ solved: true, attempts: 1, minute: 12 }))).toMatchObject({ text: "+", sub: "12'", tone: "solved" });
    expect(cellView("icpc", cell({ solved: true, attempts: 3, minute: 47 }))).toMatchObject({ text: "+2", sub: "47'" });
  });
  it("marks the first solve of a problem", () => {
    const v = cellView("icpc", cell({ solved: true, attempts: 1, minute: 5, first: true }));
    expect(v.tone).toBe("first");
    expect(v.label).toMatch(/first to solve/);
  });
  it("shows failed tries and pending (frozen) ones", () => {
    expect(cellView("icpc", cell({ attempts: 2 }))).toMatchObject({ text: "-2", tone: "failed" });
    expect(cellView("icpc", cell({ attempts: 1, pending: 1 }))).toMatchObject({ text: "?1", tone: "pending" });
    expect(cellView("icpc", cell({ pending: 2 }))).toMatchObject({ text: "?", tone: "pending" });
  });
  it("leaves untouched problems empty", () => {
    expect(cellView("icpc", undefined).tone).toBe("empty");
    expect(cellView("icpc", cell({})).tone).toBe("empty");
  });
});

describe("IOI scoreboard cells", () => {
  it("shows the best score with full, partial and zero tones", () => {
    expect(cellView("ioi", cell({ attempts: 2, score: 100 }), 100)).toMatchObject({ text: "100", tone: "solved" });
    expect(cellView("ioi", cell({ attempts: 2, score: 40 }), 100)).toMatchObject({ text: "40", tone: "partial" });
    expect(cellView("ioi", cell({ attempts: 1, score: 0 }), 100)).toMatchObject({ text: "0", tone: "failed" });
    expect(cellView("ioi", cell({ attempts: 0, pending: 1 }), 100)).toMatchObject({ text: "?", tone: "pending" });
  });
});

describe("freeze banner", () => {
  const freeze = "2026-11-01T11:00:00Z";
  it("tells contestants the board is frozen", () => {
    expect(freezeBanner({ frozen: true, freeze_at: freeze, phase: "running" }, false)?.text).toMatch(/Your own verdicts are always shown/);
    expect(freezeBanner({ frozen: true, freeze_at: freeze, phase: "ended" }, false)?.text).toMatch(/until staff reveal them/);
  });
  it("tells staff that contestants see a frozen board", () => {
    const b = freezeBanner({ frozen: false, freeze_at: freeze, phase: "running" }, true, new Date("2026-11-01T11:30:00Z"));
    expect(b?.text).toMatch(/Contestants see a frozen scoreboard/);
  });
  it("announces an upcoming freeze, and says nothing without one", () => {
    expect(freezeBanner({ frozen: false, freeze_at: freeze, phase: "running" }, false, new Date("2026-11-01T10:00:00Z"))?.text).toMatch(/freezes at/);
    expect(freezeBanner({ frozen: false, freeze_at: null, phase: "running" }, false)).toBeNull();
    expect(freezeBanner({ frozen: false, freeze_at: freeze, phase: "ended" }, false, new Date("2026-11-02T00:00:00Z"))).toBeNull();
  });
  it("labels problems A to Z in order", () => {
    expect(nextLabel([])).toBe("A");
    expect(nextLabel(["A", "B", "D"])).toBe("C");
  });
});
