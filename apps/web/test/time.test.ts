import { describe, expect, it } from "vitest";

import { formatCountdown, fromLocalInput, nextDeadline, toLocalInput, windowOf } from "@/lib/time";

describe("countdown", () => {
  it("formats minutes, hours and days, never negative", () => {
    expect(formatCountdown(9_000)).toBe("0:09");
    expect(formatCountdown(4 * 60_000 + 5_000)).toBe("4:05");
    expect(formatCountdown(3 * 3600_000 + 4 * 60_000 + 5_000)).toBe("3:04:05");
    expect(formatCountdown(2 * 86_400_000 + 3 * 3600_000)).toBe("2d 3h");
    expect(formatCountdown(-5000)).toBe("0:00");
  });
  it("knows where now falls in a window and what comes next", () => {
    const now = new Date("2026-11-01T10:30:00Z");
    expect(windowOf("2026-11-01T11:00:00Z", "2026-11-01T13:00:00Z", now)).toBe("before");
    expect(windowOf("2026-11-01T10:00:00Z", "2026-11-01T13:00:00Z", now)).toBe("during");
    expect(windowOf("2026-11-01T08:00:00Z", "2026-11-01T10:30:00Z", now)).toBe("after");
    expect(nextDeadline("2026-11-01T11:00:00Z", "2026-11-01T13:00:00Z", now)).toEqual({ label: "Starts in", ms: 30 * 60_000 });
    expect(nextDeadline("2026-11-01T10:00:00Z", "2026-11-01T11:00:00Z", now)?.label).toBe("Ends in");
    expect(nextDeadline("2026-11-01T08:00:00Z", "2026-11-01T09:00:00Z", now)).toBeNull();
  });
  it("round-trips datetime-local values with a zone for the API", () => {
    const iso = "2026-11-01T10:30:00.000Z";
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso);
    expect(fromLocalInput("")).toBeNull();
    expect(toLocalInput(null)).toBe("");
  });
});
