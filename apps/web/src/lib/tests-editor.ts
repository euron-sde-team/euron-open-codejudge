/**
 * The tests editor's model: rows typed in the browser become a version request. Names
 * follow the Kattis layout the judge reads: sample/<id>, secret/<id>, or
 * secret/<group>/<id> for a subtask group.
 */

export interface TestRow {
  key: string;
  kind: "sample" | "secret";
  /** Subtask group for hidden tests; empty means the single default group. */
  group: string;
  id: string;
  input: string;
  answer: string;
}

export interface GroupPoints {
  name: string;
  points: number;
}

const ID = /^[A-Za-z0-9_-]{1,40}$/;

export function testName(row: Pick<TestRow, "kind" | "group" | "id">): string {
  if (row.kind === "sample") return `sample/${row.id}`;
  return row.group ? `secret/${row.group}/${row.id}` : `secret/${row.id}`;
}

/** The group a row belongs to, as the API names it. */
export function groupOf(row: Pick<TestRow, "kind" | "group">): string {
  if (row.kind === "sample") return "sample";
  return row.group || "secret";
}

/** Hidden groups in first-seen order. */
export function hiddenGroups(rows: TestRow[]): string[] {
  const out: string[] = [];
  for (const r of rows) {
    const g = groupOf(r);
    if (g !== "sample" && !out.includes(g)) out.push(g);
  }
  return out;
}

/** Points for each hidden group: the ones given, the rest sharing what is left of 100. */
export function defaultPoints(groups: string[], given: Record<string, number>): GroupPoints[] {
  const assigned = groups.filter((g) => g in given).reduce((sum, g) => sum + (given[g] ?? 0), 0);
  const open = groups.filter((g) => !(g in given));
  const share = open.length ? Math.max(0, 100 - assigned) / open.length : 0;
  return groups.map((g) => ({ name: g, points: g in given ? (given[g] ?? 0) : Math.round(share * 100) / 100 }));
}

/** Problems with the rows, in plain words; empty when they can be saved. */
export function validateRows(rows: TestRow[]): string[] {
  const problems: string[] = [];
  if (!rows.some((r) => r.kind === "secret")) problems.push("Add at least one hidden test: samples alone cannot judge a solution.");
  const seen = new Set<string>();
  rows.forEach((r, i) => {
    const label = `Test ${i + 1}`;
    if (!ID.test(r.id)) problems.push(`${label}: the id may use letters, digits, - and _ only (up to 40).`);
    if (r.kind === "secret" && r.group && !ID.test(r.group)) problems.push(`${label}: the group name may use letters, digits, - and _ only.`);
    const name = testName(r);
    if (seen.has(name)) problems.push(`${label}: another test is already named ${name}.`);
    seen.add(name);
    if (!r.answer.trim()) problems.push(`${label}: the expected answer is empty.`);
  });
  return problems;
}

/** Rows rebuilt from stored test names (contents filled in separately). */
export function rowFromName(name: string, input = "", answer = ""): TestRow {
  const parts = name.split("/");
  const kind = parts[0] === "sample" ? "sample" : "secret";
  const id = parts[parts.length - 1] ?? "1";
  const group = kind === "secret" && parts.length > 2 ? parts.slice(1, -1).join("/") : "";
  return { key: name, kind, group, id, input, answer };
}

let counter = 0;
export function newRow(kind: TestRow["kind"], rows: TestRow[]): TestRow {
  counter += 1;
  const used = new Set(rows.filter((r) => r.kind === kind).map((r) => r.id));
  let n = rows.filter((r) => r.kind === kind).length + 1;
  while (used.has(String(n))) n += 1;
  return { key: `new-${counter}-${Date.now()}`, kind, group: "", id: String(n), input: "", answer: "" };
}
