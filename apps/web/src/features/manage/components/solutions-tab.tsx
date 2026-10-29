"use client";

import { CheckCircle2Icon, CircleAlertIcon, CircleDashedIcon, GavelIcon, PlusIcon, Trash2Icon } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { toast } from "sonner";

import { CodeEditor } from "@/components/code-editor";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { Hint } from "@/components/hint";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { VerdictChip } from "@/components/verdict-chip";
import { LanguageName } from "@/components/language-name";
import { useLanguages } from "@/features/problems/api";
import { errorMessage } from "@/lib/api/errors";
import type { ProblemAdmin, Reference, ReferenceIn } from "@/lib/api/types";
import { verdictSpec } from "@/lib/verdicts";

import { useAddReference, useJudgeReferences, useRemoveReference } from "../api";

const EXPECTED: ReferenceIn["expected"][] = ["AC", "WA", "TLE", "MLE", "RE"];

export function SolutionsTab({ problem: p }: { problem: ProblemAdmin }) {
  const judge = useJudgeReferences(p.id);
  const remove = useRemoveReference(p.id);
  const [adding, setAdding] = React.useState(false);
  const [removing, setRemoving] = React.useState<Reference | null>(null);
  const hasTests = p.versions.some((v) => v.current);

  return (
    <div className="space-y-4">
      <Surface>
        <SurfaceHeader
          title={
            <span className="inline-flex items-center gap-1.5">
              Reference solutions
              <Hint term="reference" />
            </span>
          }
          description="Your own solutions and the verdict each must get. Add a correct one (expected Accepted) and, ideally, a slow one that must time out, to prove the limits are right."
          action={
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                disabled={judge.isPending || !p.references.length || !hasTests}
                onClick={() =>
                  judge.mutate(undefined, {
                    onSuccess: (r) => toast.success(`Judging ${r.queued} reference solution${r.queued === 1 ? "" : "s"} on the current tests.`),
                    onError: (e) => toast.error(errorMessage(e)),
                  })
                }
              >
                <GavelIcon />
                Judge all
              </Button>
              <Button size="sm" onClick={() => setAdding(true)}>
                <PlusIcon />
                Add solution
              </Button>
            </div>
          }
        />
        {!hasTests && <p className="px-5 pb-3 text-[12.5px] text-warning">Add tests first: solutions are judged against them.</p>}
        {p.references.length ? (
          <ul className="divide-y divide-hairline px-5 pb-3">
            {p.references.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-3 py-3">
                <MatchIcon reference={r} />
                <div className="min-w-0 flex-1">
                  <div className="text-[13.5px] font-medium">{r.name}</div>
                  <div className="text-[12px] text-muted-foreground">
                    <LanguageName id={r.language} />, must get {verdictSpec(r.expected).label}
                  </div>
                </div>
                {r.last_verdict && (
                  <span className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground">
                    Got
                    {r.last_status === "done" ? <VerdictChip verdict={r.last_verdict} /> : <VerdictChip verdict="JUDGING" />}
                  </span>
                )}
                {r.last_submission_id && (
                  <Link href={`/submissions/${r.last_submission_id}`} className="text-[12.5px] font-medium text-primary hover:underline">
                    Result
                  </Link>
                )}
                <Button variant="subtle" size="icon-sm" aria-label={`Remove ${r.name}`} onClick={() => setRemoving(r)}>
                  <Trash2Icon />
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            compact
            icon={GavelIcon}
            title="No reference solution yet"
            description="A problem is published only after a solution you trust gets Accepted on its tests. It catches wrong answers in the tests before students do."
          />
        )}
      </Surface>
      {adding && <AddReference problem={p} onDone={() => setAdding(false)} />}
      <ConfirmDialog
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        title="Remove this reference solution?"
        description="It no longer counts towards publishing. Submissions already judged are not affected."
        confirmLabel="Remove"
        destructive
        pending={remove.isPending}
        onConfirm={() =>
          removing &&
          remove.mutate(removing.id, {
            onSuccess: () => setRemoving(null),
            onError: (e) => toast.error(errorMessage(e)),
          })
        }
      />
    </div>
  );
}

function MatchIcon({ reference: r }: { reference: Reference }) {
  if (r.matches === true) return <CheckCircle2Icon className="size-5 shrink-0 text-verdict-ac" aria-label="Gets its expected verdict" />;
  if (r.matches === false) return <CircleAlertIcon className="size-5 shrink-0 text-verdict-wa" aria-label="Does not get its expected verdict" />;
  return <CircleDashedIcon className="size-5 shrink-0 text-faint" aria-label="Not judged on the current tests yet" />;
}

function AddReference({ problem: p, onDone }: { problem: ProblemAdmin; onDone: () => void }) {
  const add = useAddReference(p.id);
  const languages = useLanguages();
  const [name, setName] = React.useState("correct");
  const [language, setLanguage] = React.useState("");
  const [expected, setExpected] = React.useState<ReferenceIn["expected"]>("AC");
  const [source, setSource] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const lang = languages.data?.find((l) => l.id === language) ?? languages.data?.[0];

  React.useEffect(() => {
    if (!language && languages.data?.[0]) setLanguage(languages.data[0].id);
  }, [language, languages.data]);

  function save() {
    if (!name.trim()) return setError("Name the solution, for example: correct, brute force, too slow.");
    if (!source.trim()) return setError("Paste the solution's code.");
    if (!lang) return setError("Choose a language.");
    add.mutate(
      { name: name.trim(), language: lang.id, expected, source },
      {
        onSuccess: () => {
          toast.success("Added. Judge it on the current tests next.");
          onDone();
        },
        onError: (e) => setError(errorMessage(e)),
      },
    );
  }

  return (
    <Surface className="p-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Name" htmlFor="ref-name">
          <Input id="ref-name" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Language" htmlFor="ref-lang">
          <SimpleSelect id="ref-lang" value={lang?.id ?? ""} onValueChange={setLanguage} options={(languages.data ?? []).map((l) => ({ value: l.id, label: l.name }))} />
        </Field>
        <Field label="Must get" htmlFor="ref-expected">
          <SimpleSelect
            id="ref-expected"
            value={expected ?? "AC"}
            onValueChange={(v) => setExpected((v || "AC") as ReferenceIn["expected"])}
            options={EXPECTED.map((v) => ({ value: v ?? "AC", label: verdictSpec(v).label }))}
          />
        </Field>
      </div>
      <div className="mt-4 overflow-hidden rounded-xl bg-muted/40">
        <CodeEditor value={source} onChange={setSource} language={lang?.monaco ?? "plaintext"} height={320} ariaLabel="Reference solution code" />
      </div>
      {error && <FieldError className="mt-3">{error}</FieldError>}
      <div className="mt-4 flex gap-2">
        <Button disabled={add.isPending} onClick={save}>
          {add.isPending ? "Adding..." : "Add solution"}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </Surface>
  );
}
