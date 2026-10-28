"use client";

import * as React from "react";
import { toast } from "sonner";

import { Surface } from "@/components/surface";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { errorMessage } from "@/lib/api/errors";
import type { Difficulty, ProblemAdmin } from "@/lib/api/types";
import { isSlug } from "@/lib/slug";

import { useUpdateProblem } from "../api";

/** Comma separated tags as a list: trimmed, lower case, no duplicates, at most 12. */
export function parseTags(text: string): string[] {
  const out: string[] = [];
  for (const raw of text.split(",")) {
    const t = raw.trim().toLowerCase().slice(0, 40);
    if (t && !out.includes(t)) out.push(t);
  }
  return out.slice(0, 12);
}

export function DetailsTab({ problem: p }: { problem: ProblemAdmin }) {
  const update = useUpdateProblem(p.id);
  const [title, setTitle] = React.useState(p.title);
  const [slug, setSlug] = React.useState(p.slug);
  const [difficulty, setDifficulty] = React.useState<Difficulty>(p.difficulty);
  const [tags, setTags] = React.useState(p.tags.join(", "));
  const [timeMs, setTimeMs] = React.useState(String(p.time_limit_ms));
  const [memoryMb, setMemoryMb] = React.useState(String(p.memory_limit_mb));
  const [outputMb, setOutputMb] = React.useState(String(p.output_limit_mb));
  const [visibility, setVisibility] = React.useState(p.visibility);
  const [source, setSource] = React.useState(p.source ?? "");
  const [license, setLicense] = React.useState(p.license ?? "");
  const [error, setError] = React.useState<string | null>(null);

  function save(e: React.FormEvent) {
    e.preventDefault();
    const time = Number(timeMs);
    const memory = Number(memoryMb);
    const output = Number(outputMb);
    if (!title.trim()) return setError("The title cannot be empty.");
    if (!isSlug(slug)) return setError("The slug needs 3 to 64 lower case letters, digits or hyphens.");
    if (!Number.isInteger(time) || time < 100 || time > 60000) return setError("The time limit must be between 100 and 60000 ms.");
    if (!Number.isInteger(memory) || memory < 16 || memory > 8192) return setError("The memory limit must be between 16 and 8192 MB.");
    if (!Number.isInteger(output) || output < 1 || output > 1024) return setError("The output limit must be between 1 and 1024 MB.");
    setError(null);
    update.mutate(
      {
        title: title.trim(),
        slug,
        difficulty,
        tags: parseTags(tags),
        time_limit_ms: time,
        memory_limit_mb: memory,
        output_limit_mb: output,
        visibility,
        source: source.trim() || null,
        license: license.trim() || null,
      },
      { onSuccess: () => toast.success("Details saved."), onError: (err) => setError(errorMessage(err)) },
    );
  }

  return (
    <Surface className="p-5">
      <form onSubmit={save} className="grid max-w-3xl gap-4" noValidate>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Title" htmlFor="d-title">
            <Input id="d-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label="Slug" htmlFor="d-slug" hint="Changing it changes the problem's address.">
            <Input id="d-slug" className="font-mono" value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase())} />
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Difficulty" htmlFor="d-diff">
            <SimpleSelect
              id="d-diff"
              value={difficulty}
              onValueChange={(v) => setDifficulty((v || "medium") as Difficulty)}
              options={[
                { value: "easy", label: "Easy" },
                { value: "medium", label: "Medium" },
                { value: "hard", label: "Hard" },
              ]}
            />
          </Field>
          <Field
            label="Visibility"
            htmlFor="d-vis"
            hint={visibility === "public" ? "Listed in the problems once published." : "Only reachable through contests, classes and assessments."}
          >
            <SimpleSelect
              id="d-vis"
              value={visibility}
              onValueChange={(v) => setVisibility(v === "private" ? "private" : "public")}
              options={[
                { value: "public", label: "Public" },
                { value: "private", label: "Private" },
              ]}
            />
          </Field>
        </div>
        <Field label="Tags" htmlFor="d-tags" hint="Comma separated, for example: graphs, dynamic programming.">
          <Input id="d-tags" value={tags} onChange={(e) => setTags(e.target.value)} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Time limit (ms)" htmlFor="d-time" hint="CPU time per test.">
            <Input id="d-time" inputMode="numeric" value={timeMs} onChange={(e) => setTimeMs(e.target.value)} />
          </Field>
          <Field label="Memory limit (MB)" htmlFor="d-mem">
            <Input id="d-mem" inputMode="numeric" value={memoryMb} onChange={(e) => setMemoryMb(e.target.value)} />
          </Field>
          <Field label="Output limit (MB)" htmlFor="d-out">
            <Input id="d-out" inputMode="numeric" value={outputMb} onChange={(e) => setOutputMb(e.target.value)} />
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Source (optional)" htmlFor="d-source" hint="Where the problem comes from, for credit.">
            <Input id="d-source" value={source} onChange={(e) => setSource(e.target.value)} />
          </Field>
          <Field label="Licence (optional)" htmlFor="d-license" hint="For example cc by-sa, when you share the package.">
            <Input id="d-license" value={license} onChange={(e) => setLicense(e.target.value)} />
          </Field>
        </div>
        {error && <FieldError>{error}</FieldError>}
        <div>
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? "Saving..." : "Save details"}
          </Button>
        </div>
      </form>
    </Surface>
  );
}
