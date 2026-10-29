"use client";

import { EyeIcon, FileArchiveIcon, FlaskConicalIcon, PencilIcon, PlusIcon, Trash2Icon, UploadIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { Hint } from "@/components/hint";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Dialog, DialogBody, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { LanguageName } from "@/components/language-name";
import { useLanguages } from "@/features/problems/api";
import { errorMessage } from "@/lib/api/errors";
import type { CheckerSpec, ProblemAdmin, Version } from "@/lib/api/types";
import { formatBytes } from "@/lib/format";
import { defaultPoints, groupOf, hiddenGroups, newRow, rowFromName, testName, validateRows, type TestRow } from "@/lib/tests-editor";
import { testLabel } from "@/lib/verdicts";

import { fetchTestPart, useCreateVersion, useUploadPackage } from "../api";

const PREFILL_LIMIT_BYTES = 2_000_000;

const CHECKER_LABEL: Record<string, string> = {
  tokens: "Tokens (whitespace does not matter)",
  exact: "Exact lines",
  float: "Numbers within a tolerance",
  custom: "Custom checker program",
};

export function TestsTab({ problem: p }: { problem: ProblemAdmin }) {
  const current = p.versions.find((v) => v.current) ?? null;
  const [editing, setEditing] = React.useState(false);
  const [viewing, setViewing] = React.useState<string | null>(null);

  if (editing) return <TestsEditor problem={p} current={current} onDone={() => setEditing(false)} />;

  return (
    <div className="space-y-4">
      <Surface>
        <SurfaceHeader
          title={current ? `Current tests (version ${current.number})` : "No tests yet"}
          description={
            current
              ? `${current.tests.length} tests, ${formatBytes(current.package_bytes)} package. Changing the tests creates a new version.`
              : "Add samples (shown in the statement) and hidden tests (they decide the verdict)."
          }
          action={
            <Button size="sm" onClick={() => setEditing(true)}>
              {current ? <PencilIcon /> : <PlusIcon />}
              {current ? "Edit tests" : "Write tests"}
            </Button>
          }
        />
        {current ? (
          <div className="px-5 pb-5">
            <CheckerSummary checker={current.checker} />
            <div className="mt-3 overflow-x-auto rounded-xl bg-muted/50">
              <table className="w-full min-w-[480px] text-[13px]">
                <thead>
                  <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
                    <th className="px-3 py-2 font-semibold">Test</th>
                    <th className="px-3 py-2 font-semibold">Group</th>
                    <th className="px-3 py-2 text-right font-semibold">Input</th>
                    <th className="px-3 py-2 text-right font-semibold">Answer</th>
                    <th className="w-12 px-3 py-2" aria-label="View" />
                  </tr>
                </thead>
                <tbody>
                  {current.tests.map((t) => (
                    <tr key={t.name} className="border-t border-hairline">
                      <td className="px-3 py-2">
                        {testLabel(t.name)} {t.sample && <Chip tone="info">Sample</Chip>}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {t.group}
                        {groupPoints(current, t.group)}
                      </td>
                      <td className="tabular px-3 py-2 text-right text-muted-foreground">{formatBytes(t.input_bytes)}</td>
                      <td className="tabular px-3 py-2 text-right text-muted-foreground">{formatBytes(t.answer_bytes)}</td>
                      <td className="px-3 py-2">
                        <Button variant="subtle" size="icon-xs" aria-label={`View ${t.name}`} onClick={() => setViewing(t.name)}>
                          <EyeIcon />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <EmptyState
            compact
            icon={FlaskConicalIcon}
            title="Tests decide the verdict"
            description="Write them here for small problems, or upload a Kattis package zip with data/sample and data/secret."
          />
        )}
      </Surface>
      <PackageUpload problem={p} />
      <TestViewer problemId={p.id} name={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}

function groupPoints(v: Version, group: string) {
  const g = v.groups.find((x) => x.name === group);
  if (!g || !g.points) return null;
  return <span className="ml-1.5 text-faint">({g.points} points)</span>;
}

function CheckerSummary({ checker }: { checker: CheckerSpec }) {
  const kind = checker.kind ?? "tokens";
  return (
    <p className="flex flex-wrap items-center gap-1.5 text-[13px] text-muted-foreground">
      Output check: <span className="font-medium text-foreground">{CHECKER_LABEL[kind]}</span>
      {kind === "float" && (
        <span>
          (absolute {checker.float_abs}, relative {checker.float_rel})
        </span>
      )}
      {kind === "custom" && checker.language && <span>(<LanguageName id={checker.language} />)</span>}
      <Hint term="checker" />
    </p>
  );
}

function TestViewer({ problemId, name, onClose }: { problemId: string; name: string | null; onClose: () => void }) {
  const [parts, setParts] = React.useState<{ input: string; answer: string } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    setParts(null);
    setError(null);
    if (!name) return;
    let cancelled = false;
    Promise.all([fetchTestPart(problemId, name, "input"), fetchTestPart(problemId, name, "answer")])
      .then(([input, answer]) => !cancelled && setParts({ input, answer }))
      .catch((e: unknown) => !cancelled && setError(errorMessage(e)));
    return () => {
      cancelled = true;
    };
  }, [problemId, name]);
  return (
    <Dialog open={!!name} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{name ? testLabel(name) : "Test"}</DialogTitle>
        </DialogHeader>
        <DialogBody>
          {error ? (
            <FieldError>{error}</FieldError>
          ) : !parts ? (
            <p className="text-[13px] text-muted-foreground">Loading...</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {(["input", "answer"] as const).map((part) => (
                <div key={part} className="min-w-0">
                  <div className="mb-1 text-[12px] font-semibold text-muted-foreground">{part === "input" ? "Input" : "Expected answer"}</div>
                  <pre className="max-h-80 overflow-auto rounded-lg bg-code-bg p-3 font-mono text-[12px] text-code-fg">{parts[part].slice(0, 20000)}</pre>
                </div>
              ))}
            </div>
          )}
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}

function PackageUpload({ problem: p }: { problem: ProblemAdmin }) {
  const upload = useUploadPackage(p.id);
  const inputRef = React.useRef<HTMLInputElement>(null);
  return (
    <Surface>
      <SurfaceHeader
        title="Replace the tests from a package"
        description="A Kattis package zip: data/sample and data/secret (with test_group.yaml scores for subtasks) and an optional output validator. The statement and limits stay as they are."
        action={
          <Button size="sm" variant="secondary" disabled={upload.isPending} onClick={() => inputRef.current?.click()}>
            <UploadIcon />
            {upload.isPending ? "Uploading..." : "Upload zip"}
          </Button>
        }
      />
      <input
        ref={inputRef}
        type="file"
        accept=".zip,application/zip"
        className="sr-only"
        aria-label="Package zip"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (!file) return;
          upload.mutate(file, {
            onSuccess: (v) => toast.success(`Version ${v.number} created with ${v.tests.length} tests. Judge the reference solutions again.`),
            onError: (err) => toast.error(errorMessage(err)),
          });
        }}
      />
      <div className="flex items-center gap-2 px-5 pb-4 text-[12.5px] text-muted-foreground">
        <FileArchiveIcon className="size-4" aria-hidden />
        Use this for large tests; the editor suits small problems.
      </div>
    </Surface>
  );
}

function TestsEditor({ problem: p, current, onDone }: { problem: ProblemAdmin; current: Version | null; onDone: () => void }) {
  const create = useCreateVersion(p.id);
  const languages = useLanguages();
  const [rows, setRows] = React.useState<TestRow[]>([]);
  const [loading, setLoading] = React.useState(!!current);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [points, setPoints] = React.useState<Record<string, number>>({});
  const checkerNow = (current?.checker ?? p.checker_spec) as CheckerSpec;
  const [checker, setChecker] = React.useState<CheckerSpec>({ kind: checkerNow.kind ?? "tokens", float_abs: checkerNow.float_abs ?? 1e-6, float_rel: checkerNow.float_rel ?? 1e-6, case_sensitive: checkerNow.case_sensitive ?? true, language: checkerNow.language ?? null, path: checkerNow.path ?? null });
  const [checkerSource, setCheckerSource] = React.useState("");
  const [note, setNote] = React.useState("");
  const [errors, setErrors] = React.useState<string[]>([]);

  // Load the current tests into the editor (small packages only).
  React.useEffect(() => {
    if (!current) {
      setRows([newRow("sample", []), newRow("secret", [])]);
      return;
    }
    const total = current.tests.reduce((s, t) => s + t.input_bytes + t.answer_bytes, 0);
    const given: Record<string, number> = {};
    for (const g of current.groups) if (g.name !== "sample") given[g.name] = g.points;
    setPoints(given);
    if (total > PREFILL_LIMIT_BYTES) {
      setLoading(false);
      setLoadError(`The current tests total ${formatBytes(total)}, too large to edit here. Upload a package instead, or write a new set below.`);
      setRows([newRow("sample", []), newRow("secret", [])]);
      return;
    }
    let cancelled = false;
    Promise.all(
      current.tests.map(async (t) => rowFromName(t.name, await fetchTestPart(p.id, t.name, "input"), await fetchTestPart(p.id, t.name, "answer"))),
    )
      .then((loaded) => !cancelled && setRows(loaded))
      .catch((e: unknown) => !cancelled && setLoadError(errorMessage(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [current, p.id]);

  const groups = hiddenGroups(rows);
  const groupPointsList = defaultPoints(groups, points);
  const totalPoints = groupPointsList.reduce((s, g) => s + g.points, 0);

  function update(key: string, change: Partial<TestRow>) {
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...change } : r)));
  }

  function save() {
    const problems = validateRows(rows);
    if (checker.kind === "custom" && !checker.language) problems.push("Choose the language of the custom checker.");
    if (checker.kind === "custom" && !checkerSource.trim() && !current) problems.push("Paste the custom checker's source.");
    setErrors(problems);
    if (problems.length) return;
    create.mutate(
      {
        tests: rows.map((r) => ({ name: testName(r), input: r.input, answer: r.answer })),
        groups: [
          ...(rows.some((r) => r.kind === "sample") ? [{ name: "sample", points: 0, stop_on_failure: false }] : []),
          ...groupPointsList.map((g) => ({ name: g.name, points: g.points, stop_on_failure: true })),
        ],
        checker: { ...checker, path: checker.kind === "custom" ? checker.path : null },
        checker_source: checker.kind === "custom" && checkerSource.trim() ? checkerSource : null,
        note: note.trim() || null,
      },
      {
        onSuccess: (v) => {
          toast.success(`Version ${v.number} saved. Judge the reference solutions on it before publishing.`);
          onDone();
        },
        onError: (e) => setErrors([errorMessage(e)]),
      },
    );
  }

  if (loading) return <p className="py-10 text-center text-[13px] text-muted-foreground">Loading the current tests...</p>;

  return (
    <div className="space-y-4">
      {loadError && <div className="rounded-xl bg-warning-soft px-4 py-3 text-[13px] text-warning">{loadError}</div>}
      <div className="space-y-3">
        {rows.map((r, i) => (
          <div key={r.key} className="surface p-4">
            <div className="flex flex-wrap items-end gap-3">
              <span className="text-[13px] font-semibold">Test {i + 1}</span>
              <Field label="Kind" htmlFor={`k-${r.key}`} className="w-36">
                <SimpleSelect
                  id={`k-${r.key}`}
                  size="sm"
                  value={r.kind}
                  onValueChange={(v) => update(r.key, { kind: v === "sample" ? "sample" : "secret" })}
                  options={[
                    { value: "sample", label: "Sample (shown)" },
                    { value: "secret", label: "Hidden" },
                  ]}
                />
              </Field>
              {r.kind === "secret" && (
                <Field label="Group" htmlFor={`g-${r.key}`} className="w-36">
                  <Input id={`g-${r.key}`} placeholder="default" className="h-8" value={r.group} onChange={(e) => update(r.key, { group: e.target.value })} />
                </Field>
              )}
              <Field label="Id" htmlFor={`i-${r.key}`} className="w-24">
                <Input id={`i-${r.key}`} className="h-8" value={r.id} onChange={(e) => update(r.key, { id: e.target.value })} />
              </Field>
              <span className="pb-2 font-mono text-[11.5px] text-faint">{testName(r)}</span>
              <Button variant="subtle" size="icon-sm" className="ml-auto" aria-label={`Remove test ${i + 1}`} onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}>
                <Trash2Icon />
              </Button>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Textarea aria-label={`Test ${i + 1} input`} placeholder="Input" rows={4} spellCheck={false} className="font-mono text-[12.5px]" value={r.input} onChange={(e) => update(r.key, { input: e.target.value })} />
              <Textarea aria-label={`Test ${i + 1} expected answer`} placeholder="Expected answer" rows={4} spellCheck={false} className="font-mono text-[12.5px]" value={r.answer} onChange={(e) => update(r.key, { answer: e.target.value })} />
            </div>
          </div>
        ))}
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => setRows((rs) => [...rs, newRow("sample", rs)])}>
            <PlusIcon />
            Sample
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setRows((rs) => [...rs, newRow("secret", rs)])}>
            <PlusIcon />
            Hidden test
          </Button>
        </div>
      </div>

      <Surface className="p-5">
        <div className="flex items-center gap-1.5 text-[14px] font-semibold">
          Scoring
          <Hint term="groups" />
        </div>
        <p className="mt-1 text-[12.5px] text-muted-foreground">
          Each hidden group earns its points when every test in it passes. Totals {totalPoints} points.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {groupPointsList.map((g) => (
            <Field key={g.name} label={g.name === "secret" ? "Hidden tests" : `Group ${g.name}`} htmlFor={`pts-${g.name}`}>
              <Input
                id={`pts-${g.name}`}
                inputMode="decimal"
                value={String(g.points)}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  setPoints((ps) => ({ ...ps, [g.name]: Number.isFinite(n) && n >= 0 ? n : 0 }));
                }}
              />
            </Field>
          ))}
        </div>
      </Surface>

      <Surface className="p-5">
        <div className="flex items-center gap-1.5 text-[14px] font-semibold">
          Output check
          <Hint term="checker" />
        </div>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field label="Compare by" htmlFor="checker-kind">
            <SimpleSelect
              id="checker-kind"
              value={checker.kind ?? "tokens"}
              onValueChange={(v) => setChecker((c) => ({ ...c, kind: (v || "tokens") as CheckerSpec["kind"] }))}
              options={Object.entries(CHECKER_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Field>
          {(checker.kind === "tokens" || checker.kind === "float") && (
            <label className="flex items-center gap-2 self-end pb-2 text-[13px]">
              <Switch checked={!checker.case_sensitive} onCheckedChange={(v) => setChecker((c) => ({ ...c, case_sensitive: !v }))} aria-label="Ignore letter case" />
              Ignore letter case
            </label>
          )}
          {checker.kind === "float" && (
            <>
              <Field label="Absolute tolerance" htmlFor="fabs">
                <Input id="fabs" inputMode="decimal" value={String(checker.float_abs)} onChange={(e) => setChecker((c) => ({ ...c, float_abs: Number(e.target.value) || 0 }))} />
              </Field>
              <Field label="Relative tolerance" htmlFor="frel">
                <Input id="frel" inputMode="decimal" value={String(checker.float_rel)} onChange={(e) => setChecker((c) => ({ ...c, float_rel: Number(e.target.value) || 0 }))} />
              </Field>
            </>
          )}
          {checker.kind === "custom" && (
            <Field label="Checker language" htmlFor="checker-lang" hint="Kattis convention: exit 42 accepts, 43 rejects; arguments are input, answer and a feedback folder; the output arrives on stdin.">
              <SimpleSelect
                id="checker-lang"
                value={checker.language ?? ""}
                onValueChange={(v) => setChecker((c) => ({ ...c, language: v || null }))}
                options={(languages.data ?? []).map((l) => ({ value: l.id, label: l.name }))}
              />
            </Field>
          )}
        </div>
        {checker.kind === "custom" && (
          <Textarea
            aria-label="Checker source"
            placeholder={current ? "Leave empty to keep the current checker" : "The checker's source code"}
            rows={10}
            spellCheck={false}
            className="mt-3 font-mono text-[12.5px]"
            value={checkerSource}
            onChange={(e) => setCheckerSource(e.target.value)}
          />
        )}
      </Surface>

      <Field label="Note for this version (optional)" htmlFor="v-note">
        <Input id="v-note" placeholder="For example: added large tests for n = 10^5" value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      {errors.length > 0 && (
        <ul className="list-disc space-y-0.5 rounded-xl bg-danger-soft py-3 pr-4 pl-8 text-[13px] text-danger" role="alert">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <Button disabled={create.isPending} onClick={save}>
          {create.isPending ? "Saving..." : current ? "Save as a new version" : "Save tests"}
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
      <p className="text-[12px] text-faint">
        Groups in use: {groups.map((g) => (g === "secret" ? "hidden (default)" : g)).join(", ") || "none"}. Rows: {rows.length}.{" "}
        {rows.some((r) => groupOf(r) === "sample") ? "Samples score no points." : ""}
      </p>
    </div>
  );
}
