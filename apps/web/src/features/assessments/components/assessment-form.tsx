"use client";

import { PlusIcon, Trash2Icon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import type { Assessment } from "@/lib/api/types";
import { fromLocalInput, toLocalInput } from "@/lib/time";

export interface AssessmentValues {
  title: string;
  instructions_md: string;
  duration: string;
  opens: string;
  closes: string;
  problems: { problem: string; points: string }[];
}

export function emptyAssessment(): AssessmentValues {
  return { title: "", instructions_md: "", duration: "60", opens: "", closes: "", problems: [{ problem: "", points: "100" }] };
}

export function fromAssessment(a: Assessment): AssessmentValues {
  return {
    title: a.title,
    instructions_md: a.instructions_md,
    duration: String(a.duration_minutes),
    opens: toLocalInput(a.opens_at),
    closes: toLocalInput(a.closes_at),
    problems: a.problems.map((p) => ({ problem: p.slug, points: String(p.points) })),
  };
}

export function assessmentPayload(v: AssessmentValues):
  | { ok: true; body: { title: string; instructions_md: string; duration_minutes: number; opens_at: string | null; closes_at: string | null; problems: { problem: string; points: number }[] } }
  | { ok: false; error: string } {
  if (!v.title.trim()) return { ok: false, error: "Give the assessment a title." };
  const duration = Number(v.duration);
  if (!Number.isInteger(duration) || duration < 1 || duration > 1440) return { ok: false, error: "The duration must be 1 to 1440 minutes." };
  const opens = v.opens ? fromLocalInput(v.opens) : null;
  const closes = v.closes ? fromLocalInput(v.closes) : null;
  if (opens && closes && closes <= opens) return { ok: false, error: "The window must close after it opens." };
  const problems = v.problems.filter((p) => p.problem.trim()).map((p) => ({ problem: p.problem.trim(), points: Number(p.points) }));
  if (!problems.length) return { ok: false, error: "Add at least one problem (by its slug)." };
  if (problems.some((p) => !Number.isFinite(p.points) || p.points < 0)) return { ok: false, error: "Points must be zero or more." };
  return { ok: true, body: { title: v.title.trim(), instructions_md: v.instructions_md, duration_minutes: duration, opens_at: opens, closes_at: closes, problems } };
}

export function AssessmentFields({ values, onChange }: { values: AssessmentValues; onChange: (v: AssessmentValues) => void }) {
  const set = <K extends keyof AssessmentValues>(key: K, value: AssessmentValues[K]) => onChange({ ...values, [key]: value });
  const setProblem = (i: number, change: Partial<{ problem: string; points: string }>) => set("problems", values.problems.map((p, j) => (j === i ? { ...p, ...change } : p)));
  return (
    <div className="grid gap-4">
      <Field label="Title" htmlFor="as-title">
        <Input id="as-title" value={values.title} onChange={(e) => set("title", e.target.value)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Duration (minutes)" htmlFor="as-dur" hint="The clock starts when the candidate opens the link.">
          <Input id="as-dur" inputMode="numeric" value={values.duration} onChange={(e) => set("duration", e.target.value)} />
        </Field>
        <Field label="Opens (optional)" htmlFor="as-open">
          <Input id="as-open" type="datetime-local" value={values.opens} onChange={(e) => set("opens", e.target.value)} />
        </Field>
        <Field label="Closes (optional)" htmlFor="as-close" hint="No one can start or continue after it.">
          <Input id="as-close" type="datetime-local" value={values.closes} onChange={(e) => set("closes", e.target.value)} />
        </Field>
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
      <Field label="Instructions for candidates (Markdown)" htmlFor="as-inst" hint="Shown before they start the clock.">
        <Textarea id="as-inst" rows={5} value={values.instructions_md} onChange={(e) => set("instructions_md", e.target.value)} />
      </Field>
    </div>
  );
}
