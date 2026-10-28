import { describe, expect, it } from "vitest";

import { parseTags } from "@/features/manage/components/details-tab";
import { isSlug, slugify } from "@/lib/slug";
import { defaultPoints, groupOf, hiddenGroups, newRow, rowFromName, testName, validateRows, type TestRow } from "@/lib/tests-editor";

const row = (over: Partial<TestRow>): TestRow => ({ key: Math.random().toString(), kind: "secret", group: "", id: "1", input: "1", answer: "1", ...over });

describe("tests editor model", () => {
  it("names tests in the Kattis layout", () => {
    expect(testName({ kind: "sample", group: "x", id: "1" })).toBe("sample/1");
    expect(testName({ kind: "secret", group: "", id: "2" })).toBe("secret/2");
    expect(testName({ kind: "secret", group: "g1", id: "3" })).toBe("secret/g1/3");
    expect(groupOf({ kind: "secret", group: "" })).toBe("secret");
  });
  it("rebuilds rows from stored names", () => {
    expect(rowFromName("secret/g2/07", "in", "out")).toMatchObject({ kind: "secret", group: "g2", id: "07", input: "in", answer: "out" });
    expect(rowFromName("sample/1")).toMatchObject({ kind: "sample", group: "", id: "1" });
  });
  it("finds hidden groups and shares the remaining points", () => {
    const rows = [row({ kind: "sample" }), row({ group: "g1" }), row({ group: "g2", id: "2" }), row({ group: "g1", id: "3" })];
    expect(hiddenGroups(rows)).toEqual(["g1", "g2"]);
    expect(defaultPoints(["g1", "g2"], {})).toEqual([
      { name: "g1", points: 50 },
      { name: "g2", points: 50 },
    ]);
    expect(defaultPoints(["g1", "g2", "g3"], { g1: 40 })).toEqual([
      { name: "g1", points: 40 },
      { name: "g2", points: 30 },
      { name: "g3", points: 30 },
    ]);
  });
  it("refuses sets that cannot judge, duplicate names and empty answers", () => {
    expect(validateRows([row({ kind: "sample" })])[0]).toMatch(/at least one hidden test/);
    expect(validateRows([row({}), row({})]).join(" ")).toMatch(/already named secret\/1/);
    expect(validateRows([row({ answer: "  " })]).join(" ")).toMatch(/expected answer is empty/);
    expect(validateRows([row({ id: "bad id" })]).join(" ")).toMatch(/letters, digits/);
    expect(validateRows([row({}), row({ kind: "sample" })])).toEqual([]);
  });
  it("numbers new rows after the existing ones", () => {
    const rows = [row({ id: "1" }), row({ id: "2" })];
    expect(newRow("secret", rows).id).toBe("3");
    expect(newRow("sample", rows).id).toBe("1");
  });
});

describe("slugs and tags", () => {
  it("derives a valid slug from a title", () => {
    expect(slugify("Two Sum: the Return!")).toBe("two-sum-the-return");
    expect(slugify("  Café au lait  ")).toBe("cafe-au-lait");
    expect(isSlug(slugify("Shortest Paths in Graphs"))).toBe(true);
    expect(isSlug("a")).toBe(false);
    expect(isSlug("-bad-")).toBe(false);
  });
  it("cleans comma separated tags", () => {
    expect(parseTags("Graphs, dp, graphs, , BFS ")).toEqual(["graphs", "dp", "bfs"]);
  });
});
