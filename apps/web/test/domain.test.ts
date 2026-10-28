import { describe, expect, it } from "vitest";

import { assessmentPayload, emptyAssessment } from "@/features/assessments/components/assessment-form";
import { timeline } from "@/features/assessments/components/report-screen";
import { assignmentPayload, emptyAssignment } from "@/features/classes/components/assignment-form";
import { contestPayload, emptyContest } from "@/features/contests/components/contest-form";
import { dailySeries, verdictColor, verdictSlices } from "@/lib/analytics";
import { gradebookCsvUrl, latePolicyText } from "@/lib/classes";
import { parseCandidates } from "@/lib/invites";
import { NAV_ITEMS, visibleTo } from "@/lib/nav";
import { highlightedLines, similarityLabel, similarityTone } from "@/lib/plagiarism";

describe("classes", () => {
  it("explains late policies plainly", () => {
    expect(latePolicyText("accept", 0)).toBe("Late work counts in full.");
    expect(latePolicyText("penalty", 20)).toBe("Late work counts, minus 20% of its score.");
    expect(latePolicyText("penalty", 100)).toBe("Late work scores nothing.");
    expect(latePolicyText("refuse", 0)).toMatch(/not accepted/);
  });
  it("links the gradebook CSV", () => {
    expect(gradebookCsvUrl("abc-123")).toBe("/api/v1/assignments/abc-123/gradebook.csv");
  });
});

describe("analytics series", () => {
  it("zero-fills every day of the window, oldest first", () => {
    const s = dailySeries([{ day: "2026-10-27", submissions: 5, accepted: 2 }], 3, new Date("2026-10-28T12:00:00Z"));
    expect(s.map((d) => d.day)).toEqual(["2026-10-26", "2026-10-27", "2026-10-28"]);
    expect(s[1]).toEqual({ day: "2026-10-27", submissions: 5, accepted: 2, rejected: 3 });
    expect(s[0]!.submissions).toBe(0);
  });
  it("orders verdicts and computes shares, skipping empty ones", () => {
    const slices = verdictSlices({ AC: 6, WA: 3, TLE: 1, MLE: 0, RE: 0, CE: 0, OLE: 0, IE: 0 });
    expect(slices.map((v) => v.verdict)).toEqual(["AC", "WA", "TLE"]);
    expect(slices[0]!.share).toBeCloseTo(0.6);
    expect(verdictColor("AC")).toBe("var(--verdict-ac)");
  });
});

describe("invitations", () => {
  it("reads emails, names and both formats, dropping duplicates", () => {
    const { candidates, invalid } = parseCandidates("Ada Lovelace <Ada@Example.com>\nalan@example.com\nGrace Hopper, grace@example.com\nada@example.com\n\nnot an email");
    expect(candidates).toEqual([
      { email: "ada@example.com", name: "Ada Lovelace" },
      { email: "alan@example.com", name: "" },
      { email: "grace@example.com", name: "Grace Hopper" },
    ]);
    expect(invalid).toEqual(["not an email"]);
  });
});

describe("plagiarism", () => {
  it("highlights matched line ranges within the file", () => {
    expect([...highlightedLines([[2, 4], [9, 12]], 10)].sort((a, b) => a - b)).toEqual([2, 3, 4, 9, 10]);
    expect(highlightedLines([[0, 1]], 5).has(1)).toBe(true);
  });
  it("labels and grades similarity", () => {
    expect(similarityLabel(0.873)).toBe("87%");
    expect(similarityTone(0.85)).toBe("danger");
    expect(similarityTone(0.65)).toBe("warning");
    expect(similarityTone(0.4)).toBe("neutral");
  });
});

describe("forms", () => {
  it("validates contests before sending", () => {
    const v = { ...emptyContest(), title: "Weekly round" };
    expect(contestPayload(v).ok).toBe(true);
    expect(contestPayload({ ...v, title: " " })).toEqual({ ok: false, error: "Give the contest a title." });
    expect(contestPayload({ ...v, ends: v.starts })).toMatchObject({ ok: false });
    expect(contestPayload({ ...v, freeze: "2000-01-01T00:00" })).toEqual({ ok: false, error: "The freeze must fall inside the contest." });
  });
  it("validates assignments before sending", () => {
    const v = { ...emptyAssignment(), title: "Week 1", problems: [{ problem: "sum", points: "50" }, { problem: " ", points: "10" }] };
    const p = assignmentPayload(v);
    expect(p.ok && p.body.problems).toEqual([{ problem: "sum", points: 50 }]);
    expect(assignmentPayload({ ...v, problems: [{ problem: "", points: "1" }] })).toMatchObject({ ok: false });
    expect(assignmentPayload({ ...v, penalty: "120" })).toMatchObject({ ok: false });
  });
  it("validates assessments before sending", () => {
    const v = { ...emptyAssessment(), title: "Backend screen", problems: [{ problem: "sum", points: "100" }] };
    expect(assessmentPayload(v)).toMatchObject({ ok: true, body: { duration_minutes: 60, opens_at: null } });
    expect(assessmentPayload({ ...v, duration: "0" })).toMatchObject({ ok: false });
  });
});

describe("candidate report", () => {
  it("merges submissions and events in time order", () => {
    const sub = (id: string, at: string) => ({ id, created_at: at }) as never;
    const items = timeline({
      submissions: [sub("s2", "2026-10-28T10:20:00Z"), sub("s1", "2026-10-28T10:05:00Z")],
      events: [{ kind: "paste", at: "2026-10-28T10:10:00Z", detail: {} }],
    });
    expect(items.map((i) => (i.kind === "submission" ? (i.sub as { id: string }).id : i.event.kind))).toEqual(["s1", "paste", "s2"]);
  });
});

describe("navigation for the new areas", () => {
  const item = (href: string) => NAV_ITEMS.find((i) => i.href === href)!;
  it("shows each area to the right people", () => {
    expect(visibleTo(item("/contests"), null)).toBe(true);
    expect(visibleTo(item("/classes"), "student")).toBe(true);
    expect(visibleTo(item("/progress"), "student")).toBe(true);
    expect(visibleTo(item("/progress"), "staff")).toBe(false);
    expect(visibleTo(item("/assessments"), "student")).toBe(false);
    expect(visibleTo(item("/plagiarism"), "staff")).toBe(true);
    expect(visibleTo(item("/analytics"), "admin")).toBe(true);
    expect(visibleTo(item("/admin/settings"), "staff")).toBe(false);
  });
});
