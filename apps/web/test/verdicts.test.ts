import { describe, expect, it } from "vitest";

import { formatMemory, formatScore, formatTime, isFinal, testLabel, verdictSpec } from "@/lib/verdicts";

describe("verdicts", () => {
  it("names every verdict in plain words with its own colour", () => {
    expect(verdictSpec("AC").label).toBe("Accepted");
    expect(verdictSpec("TLE").label).toBe("Time limit exceeded");
    expect(verdictSpec("CE").hint).toMatch(/compiler output/);
    expect(verdictSpec("AC").className).toContain("verdict-ac");
    expect(verdictSpec("WA").className).toContain("verdict-wa");
  });
  it("blames the judge, not the person, for an internal error", () => {
    expect(verdictSpec("IE").hint).toMatch(/judge failed, not your program/);
  });
  it("treats unknown and missing verdicts gracefully", () => {
    expect(verdictSpec("XYZ").label).toBe("XYZ");
    expect(verdictSpec(null).code).toBe("PENDING");
  });
  it("knows which verdicts are final", () => {
    expect(isFinal("AC")).toBe(true);
    expect(isFinal("IE")).toBe(true);
    expect(isFinal("PENDING")).toBe(false);
    expect(isFinal("JUDGING")).toBe(false);
    expect(isFinal(undefined)).toBe(false);
  });
});

describe("measurements", () => {
  it("formats CPU time", () => {
    expect(formatTime(12)).toBe("12 ms");
    expect(formatTime(1240)).toBe("1.24 s");
    expect(formatTime(12500)).toBe("12.5 s");
    expect(formatTime(null)).toBe("n/a");
  });
  it("formats memory from KB", () => {
    expect(formatMemory(812)).toBe("812 KB");
    expect(formatMemory(12_700)).toBe("12.4 MB");
    expect(formatMemory(300 * 1024)).toBe("300 MB");
  });
  it("formats scores without trailing zeros", () => {
    expect(formatScore(40, 100)).toBe("40 / 100");
    expect(formatScore(33.3333, 100)).toBe("33.33 / 100");
    expect(formatScore(7, 0)).toBe("7");
    expect(formatScore(null, 100)).toBe("n/a");
  });
  it("labels tests for people", () => {
    expect(testLabel("sample/1")).toBe("Sample 1");
    expect(testLabel("secret/g1/03")).toBe("Hidden g1/03");
    expect(testLabel("other")).toBe("other");
  });
});
