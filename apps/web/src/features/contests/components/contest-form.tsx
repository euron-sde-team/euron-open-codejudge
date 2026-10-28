"use client";

import * as React from "react";

import { Input, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import type { Contest, ContestFormat } from "@/lib/api/types";
import { FORMAT_LABEL } from "@/lib/contest";
import { fromLocalInput, toLocalInput } from "@/lib/time";

export interface ContestFormValues {
  title: string;
  slug: string;
  description_md: string;
  format: ContestFormat;
  starts: string;
  ends: string;
  freeze: string;
  visibility: "public" | "private";
  registration: "open" | "invite";
  penalty: string;
}

export function emptyContest(): ContestFormValues {
  const start = new Date(Date.now() + 24 * 3600_000);
  start.setMinutes(0, 0, 0);
  const end = new Date(start.getTime() + 2 * 3600_000);
  return {
    title: "",
    slug: "",
    description_md: "",
    format: "icpc",
    starts: toLocalInput(start.toISOString()),
    ends: toLocalInput(end.toISOString()),
    freeze: "",
    visibility: "public",
    registration: "open",
    penalty: "20",
  };
}

export function fromContest(c: Contest): ContestFormValues {
  return {
    title: c.title,
    slug: c.slug,
    description_md: c.description_md,
    format: c.format,
    starts: toLocalInput(c.starts_at),
    ends: toLocalInput(c.ends_at),
    freeze: toLocalInput(c.freeze_at),
    visibility: c.visibility === "private" ? "private" : "public",
    registration: c.registration === "invite" ? "invite" : "open",
    penalty: String(c.penalty_minutes),
  };
}

/** Check the form and build the request fields, or say what to fix. */
export function contestPayload(v: ContestFormValues):
  | { ok: true; body: { title: string; description_md: string; format: ContestFormat; starts_at: string; ends_at: string; freeze_at: string | null; visibility: "public" | "private"; registration: "open" | "invite"; penalty_minutes: number } }
  | { ok: false; error: string } {
  if (!v.title.trim()) return { ok: false, error: "Give the contest a title." };
  const starts = fromLocalInput(v.starts);
  const ends = fromLocalInput(v.ends);
  if (!starts || !ends) return { ok: false, error: "Set when the contest starts and ends." };
  if (ends <= starts) return { ok: false, error: "The contest must end after it starts." };
  const freeze = v.freeze ? fromLocalInput(v.freeze) : null;
  if (freeze && (freeze < starts || freeze > ends)) return { ok: false, error: "The freeze must fall inside the contest." };
  const penalty = Number(v.penalty);
  if (!Number.isInteger(penalty) || penalty < 0 || penalty > 240) return { ok: false, error: "The penalty must be 0 to 240 minutes." };
  return {
    ok: true,
    body: { title: v.title.trim(), description_md: v.description_md, format: v.format, starts_at: starts, ends_at: ends, freeze_at: freeze, visibility: v.visibility, registration: v.registration, penalty_minutes: penalty },
  };
}

export function ContestFields({ values, onChange, withSlug }: { values: ContestFormValues; onChange: (v: ContestFormValues) => void; withSlug: boolean }) {
  const set = <K extends keyof ContestFormValues>(key: K, value: ContestFormValues[K]) => onChange({ ...values, [key]: value });
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Title" htmlFor="c-title">
          <Input id="c-title" value={values.title} onChange={(e) => set("title", e.target.value)} />
        </Field>
        {withSlug && (
          <Field label="Slug" htmlFor="c-slug" hint="The contest's address: /contests/your-slug.">
            <Input id="c-slug" className="font-mono" value={values.slug} onChange={(e) => set("slug", e.target.value.toLowerCase())} />
          </Field>
        )}
      </div>
      <Field label="Format" htmlFor="c-format" hint={FORMAT_LABEL[values.format]}>
        <SimpleSelect
          id="c-format"
          value={values.format}
          onValueChange={(v) => set("format", v === "ioi" ? "ioi" : "icpc")}
          options={[
            { value: "icpc", label: "ICPC" },
            { value: "ioi", label: "IOI" },
          ]}
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Starts" htmlFor="c-start">
          <Input id="c-start" type="datetime-local" value={values.starts} onChange={(e) => set("starts", e.target.value)} />
        </Field>
        <Field label="Ends" htmlFor="c-end">
          <Input id="c-end" type="datetime-local" value={values.ends} onChange={(e) => set("ends", e.target.value)} />
        </Field>
        <Field label="Scoreboard freeze (optional)" htmlFor="c-freeze" hint="After it, others' results show as pending.">
          <Input id="c-freeze" type="datetime-local" value={values.freeze} onChange={(e) => set("freeze", e.target.value)} />
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Visibility" htmlFor="c-vis" hint={values.visibility === "public" ? "Listed for everyone." : "Only people with the join code see it."}>
          <SimpleSelect
            id="c-vis"
            value={values.visibility}
            onValueChange={(v) => set("visibility", v === "private" ? "private" : "public")}
            options={[
              { value: "public", label: "Public" },
              { value: "private", label: "Private" },
            ]}
          />
        </Field>
        <Field label="Registration" htmlFor="c-reg" hint={values.registration === "open" ? "Anyone signed in can register." : "Only with the join code."}>
          <SimpleSelect
            id="c-reg"
            value={values.registration}
            onValueChange={(v) => set("registration", v === "invite" ? "invite" : "open")}
            options={[
              { value: "open", label: "Open" },
              { value: "invite", label: "Join code only" },
            ]}
          />
        </Field>
        {values.format === "icpc" && (
          <Field label="Penalty per wrong try (min)" htmlFor="c-pen">
            <Input id="c-pen" inputMode="numeric" value={values.penalty} onChange={(e) => set("penalty", e.target.value)} />
          </Field>
        )}
      </div>
      <Field label="Description (Markdown, optional)" htmlFor="c-desc">
        <Textarea id="c-desc" rows={4} value={values.description_md} onChange={(e) => set("description_md", e.target.value)} />
      </Field>
    </div>
  );
}
