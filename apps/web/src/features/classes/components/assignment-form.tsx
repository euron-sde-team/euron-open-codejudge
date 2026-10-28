"use client";

import { PlusIcon, Trash2Icon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import type { Assignment, LatePolicy } from "@/lib/api/types";
import { latePolicyText } from "@/lib/classes";
import { fromLocalInput, toLocalInput } from "@/lib/time";

export interface AssignmentValues {
  title: string;
  description_md: string;
  opens: string;
  due: string;
  late_policy: LatePolicy;
  penalty: string;
  problems: { problem: string; points: string }[];
}

export function emptyAssignment(): AssignmentValues {
  const opens = new Date();
  opens.setMinutes(0, 0, 0);
  const due = new Date(opens.getTime() + 7 * 86_400_000);
  return {
    title: "",
    description_md: "",
    opens: toLocalInput(opens.toISOString()),
    due: toLocalInput(due.toISOString()),
    late_policy: "penalty",
    penalty: "20",
    problems: [{ problem: "", points: "100" }],
  };
}

export function fromAssignment(a: Assignment): AssignmentValues {
  return {
    title: a.title,
    description_md: a.description_md,
    opens: toLocalInput(a.opens_at),
    due: toLocalInput(a.due_at),
    late_policy: a.late_policy,
    penalty: String(a.penalty_percent),
    problems: a.problems.map((p) => ({ problem: p.slug, points: String(p.points) })),
  };
}

export function assignmentPayload(v: AssignmentValues):
  | { ok: true; body: { title: string; description_md: string; opens_at: string; due_at: string; late_policy: LatePolicy; penalty_percent: number; problems: { problem: string; points: number }[] } }
  | { ok: false; error: string } {
  if (!v.title.trim()) return { ok: false, error: "Give the assignment a title." };
  const opens = fromLocalInput(v.opens);
  const due = fromLocalInput(v.due);
  if (!opens || !due) return { ok: false, error: "Set when it opens and when it is due." };
  if (due <= opens) return { ok: false, error: "The due time must be after the opening time." };
  const penalty = Number(v.penalty);
  if (!Number.isInteger(penalty) || penalty < 0 || penalty > 100) return { ok: false, error: "The late penalty must be 0 to 100 percent." };
  const problems = v.problems.filter((p) => p.problem.trim()).map((p) => ({ problem: p.problem.trim(), points: Number(p.points) }));
  if (!problems.length) return { ok: false, error: "Add at least one problem (by its slug)." };
  if (problems.some((p) => !Number.isFinite(p.points) || p.points < 0)) return { ok: false, error: "Points must be zero or more." };
  return { ok: true, body: { title: v.title.trim(), description_md: v.description_md, opens_at: opens, due_at: due, late_policy: v.late_policy, penalty_percent: penalty, problems } };
}

export function AssignmentFields({ values, onChange }: { values: AssignmentValues; onChange: (v: AssignmentValues) => void }) {
  const set = <K extends keyof AssignmentValues>(key: K, value: AssignmentValues[K]) => onChange({ ...values, [key]: value });
  const setProblem = (i: number, change: Partial<{ problem: string; points: string }>) =>
    set("problems", values.problems.map((p, j) => (j === i ? { ...p, ...change } : p)));
  return (
    <div className="grid gap-4">
      <Field label="Title" htmlFor="a-title">
        <Input id="a-title" value={values.title} onChange={(e) => set("title", e.target.value)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Opens" htmlFor="a-opens">
          <Input id="a-opens" type="datetime-local" value={values.opens} onChange={(e) => set("opens", e.target.value)} />
        </Field>
        <Field label="Due" htmlFor="a-due">
          <Input id="a-due" type="datetime-local" value={values.due} onChange={(e) => set("due", e.target.value)} />
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Late work" htmlFor="a-late" hint={latePolicyText(values.late_policy, Number(values.penalty) || 0)}>
          <SimpleSelect
            id="a-late"
            value={values.late_policy}
            onValueChange={(v) => set("late_policy", (v || "penalty") as LatePolicy)}
            options={[
              { value: "accept", label: "Accept in full" },
              { value: "penalty", label: "Accept with a penalty" },
              { value: "refuse", label: "Refuse" },
            ]}
          />
        </Field>
        {values.late_policy === "penalty" && (
          <Field label="Penalty (percent of the score)" htmlFor="a-pen">
            <Input id="a-pen" inputMode="numeric" value={values.penalty} onChange={(e) => set("penalty", e.target.value)} />
          </Field>
        )}
      </div>
      <div>
        <div className="mb-1.5 text-[13px] font-medium">Problems</div>
        <div className="space-y-2">
          {values.problems.map((p, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input aria-label={`Problem ${i + 1} slug`} placeholder="problem-slug" className="font-mono" value={p.problem} onChange={(e) => setProblem(i, { problem: e.target.value })} />
              <Input aria-label={`Problem ${i + 1} points`} inputMode="decimal" className="w-24" value={p.points} onChange={(e) => setProblem(i, { points: e.target.value })} />
              <Button variant="subtle" size="icon-sm" aria-label={`Remove problem ${i + 1}`} disabled={values.problems.length === 1} onClick={() => set("problems", values.problems.filter((_, j) => j !== i))}>
                <Trash2Icon />
              </Button>
            </div>
          ))}
          <Button variant="secondary" size="sm" onClick={() => set("problems", [...values.problems, { problem: "", points: "100" }])}>
            <PlusIcon />
            Add problem
          </Button>
        </div>
      </div>
      <Field label="Instructions (Markdown, optional)" htmlFor="a-desc">
        <Textarea id="a-desc" rows={4} value={values.description_md} onChange={(e) => set("description_md", e.target.value)} />
      </Field>
    </div>
  );
}
