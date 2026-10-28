"use client";

import { FileArchiveIcon, FileCode2Icon, PlusIcon, UploadIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { AdminOnly } from "@/components/admin-only";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Segmented } from "@/components/segmented";
import { TableSkeleton } from "@/components/table-skeleton";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { usePermissions } from "@/features/auth/api";
import { useProblems } from "@/features/problems/api";
import { errorMessage } from "@/lib/api/errors";
import type { Difficulty, ImportResult } from "@/lib/api/types";
import { formatNumber, formatRelative } from "@/lib/format";
import { isSlug, slugify } from "@/lib/slug";
import { DIFFICULTY } from "@/lib/verdicts";

import { useCreateProblem, useImportProblem } from "../api";

type StatusFilter = "all" | "draft" | "published";

export function ManageProblemsScreen() {
  const { user, staff } = usePermissions();
  const [status, setStatus] = React.useState<StatusFilter>("all");
  const [createOpen, setCreateOpen] = React.useState(false);
  const [importOpen, setImportOpen] = React.useState(false);
  const list = useProblems({ status: status === "all" ? "" : status, limit: 200 });

  if (user && !staff) return <AdminOnly what="The problem editor" />;

  return (
    <>
      <PageHeader
        title="Problem editor"
        description="Write problems, add tests and a reference solution, and publish them once the solution passes."
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setImportOpen(true)}>
              <UploadIcon />
              Import package
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <PlusIcon />
              New problem
            </Button>
          </div>
        }
      />
      <div className="mb-4">
        <Segmented<StatusFilter>
          ariaLabel="Status"
          value={status}
          onChange={setStatus}
          options={[
            { value: "all", label: "All" },
            { value: "draft", label: "Drafts" },
            { value: "published", label: "Published" },
          ]}
        />
      </div>
      <div className="surface overflow-x-auto">
        {list.isPending ? (
          <TableSkeleton rows={6} cols={5} />
        ) : list.isError ? (
          <ErrorState error={list.error} title="Problems could not be loaded" onRetry={() => void list.refetch()} />
        ) : !list.data.items.length ? (
          <EmptyState
            icon={FileCode2Icon}
            title={status === "all" ? "No problems yet" : status === "draft" ? "No drafts" : "Nothing published yet"}
            description="A problem is a statement, tests (samples and hidden ones) and a reference solution that must pass before it is published. Start one here, or import a Kattis package zip."
            action={
              <Button onClick={() => setCreateOpen(true)}>
                <PlusIcon />
                New problem
              </Button>
            }
          />
        ) : (
          <table className="w-full min-w-[560px] text-[13px]">
            <thead>
              <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
                <th className="px-4 py-2.5 font-semibold">Problem</th>
                <th className="px-3 py-2.5 font-semibold">Status</th>
                <th className="px-3 py-2.5 font-semibold">Difficulty</th>
                <th className="px-3 py-2.5 text-right font-semibold">Submissions</th>
                <th className="px-3 py-2.5 text-right font-semibold">Updated</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((p) => (
                <tr key={p.id} className="border-t border-hairline hover:bg-muted/40">
                  <td className="px-4 py-2.5">
                    <Link href={`/manage/problems/${p.id}`} className="font-medium text-primary hover:underline">
                      {p.title}
                    </Link>
                    <div className="font-mono text-[11.5px] text-faint">{p.slug}</div>
                  </td>
                  <td className="px-3 py-2.5">
                    {p.status === "published" ? (
                      <Chip tone="success">{p.visibility === "private" ? "Published, private" : "Published"}</Chip>
                    ) : (
                      <Chip tone="warning">Draft</Chip>
                    )}
                  </td>
                  <td className={`px-3 py-2.5 font-semibold ${DIFFICULTY[p.difficulty]?.className ?? ""}`}>{DIFFICULTY[p.difficulty]?.label}</td>
                  <td className="tabular px-3 py-2.5 text-right text-muted-foreground">{formatNumber(p.submissions_count)}</td>
                  <td className="px-3 py-2.5 text-right text-muted-foreground">{formatRelative(p.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <CreateProblemDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} />
    </>
  );
}

function CreateProblemDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const create = useCreateProblem();
  const [title, setTitle] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [slugTouched, setSlugTouched] = React.useState(false);
  const [difficulty, setDifficulty] = React.useState<Difficulty>("medium");
  const [timeMs, setTimeMs] = React.useState("2000");
  const [memoryMb, setMemoryMb] = React.useState("256");
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setTitle("");
      setSlug("");
      setSlugTouched(false);
      setDifficulty("medium");
      setTimeMs("2000");
      setMemoryMb("256");
      setError(null);
    }
  }, [open]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return setError("Give the problem a title.");
    if (!isSlug(slug)) return setError("The slug needs 3 to 64 lower case letters, digits or hyphens, starting and ending with a letter or digit.");
    const time = Number(timeMs);
    const memory = Number(memoryMb);
    if (!Number.isInteger(time) || time < 100 || time > 60000) return setError("The time limit must be between 100 and 60000 ms.");
    if (!Number.isInteger(memory) || memory < 16 || memory > 8192) return setError("The memory limit must be between 16 and 8192 MB.");
    create.mutate(
      { title: title.trim(), slug, difficulty, time_limit_ms: time, memory_limit_mb: memory, statement_md: "" },
      {
        onSuccess: (p) => {
          toast.success("Problem created as a draft. Next: write the statement and add tests.");
          onOpenChange(false);
          router.push(`/manage/problems/${p.id}`);
        },
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !create.isPending && onOpenChange(o)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New problem</DialogTitle>
          <DialogDescription>It starts as a draft only staff can see. You add the statement, tests and a reference solution next.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogBody className="space-y-4">
            <Field label="Title" htmlFor="p-title">
              <Input
                id="p-title"
                autoFocus
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  if (!slugTouched) setSlug(slugify(e.target.value));
                }}
              />
            </Field>
            <Field label="Slug" htmlFor="p-slug" hint="The problem's address: /problems/your-slug.">
              <Input
                id="p-slug"
                className="font-mono"
                value={slug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setSlug(e.target.value.toLowerCase());
                }}
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Difficulty" htmlFor="p-diff">
                <SimpleSelect
                  id="p-diff"
                  value={difficulty}
                  onValueChange={(v) => setDifficulty((v || "medium") as Difficulty)}
                  options={[
                    { value: "easy", label: "Easy" },
                    { value: "medium", label: "Medium" },
                    { value: "hard", label: "Hard" },
                  ]}
                />
              </Field>
              <Field label="Time limit (ms)" htmlFor="p-time">
                <Input id="p-time" inputMode="numeric" value={timeMs} onChange={(e) => setTimeMs(e.target.value)} />
              </Field>
              <Field label="Memory (MB)" htmlFor="p-mem">
                <Input id="p-mem" inputMode="numeric" value={memoryMb} onChange={(e) => setMemoryMb(e.target.value)} />
              </Field>
            </div>
            {error && <FieldError>{error}</FieldError>}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating..." : "Create draft"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ImportDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const importProblem = useImportProblem();
  const [file, setFile] = React.useState<File | null>(null);
  const [slug, setSlug] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<ImportResult | null>(null);

  React.useEffect(() => {
    if (open) {
      setFile(null);
      setSlug("");
      setError(null);
      setResult(null);
    }
  }, [open]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return setError("Choose a package zip first.");
    if (slug && !isSlug(slug)) return setError("The slug needs 3 to 64 lower case letters, digits or hyphens.");
    importProblem.mutate(
      { file, slug: slug || undefined },
      { onSuccess: setResult, onError: (err) => setError(errorMessage(err)) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !importProblem.isPending && onOpenChange(o)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Import a problem package</DialogTitle>
          <DialogDescription>
            A zip in the Kattis problem package format (problem.yaml, problem_statement, data/sample and data/secret). It imports as
            a draft.
          </DialogDescription>
        </DialogHeader>
        {result ? (
          <>
            <DialogBody className="space-y-3">
              <div className="rounded-lg bg-savings-soft px-3.5 py-2.5 text-[13px] text-savings">
                Imported <strong>{result.problem.title}</strong>: {result.tests} tests in {result.groups} groups, {result.references} reference
                solution{result.references === 1 ? "" : "s"}.
              </div>
              {result.warnings.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-[13px] text-warning">
                  {result.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}
            </DialogBody>
            <DialogFooter>
              <Button
                onClick={() => {
                  onOpenChange(false);
                  router.push(`/manage/problems/${result.problem.id}`);
                }}
              >
                Open in the editor
              </Button>
            </DialogFooter>
          </>
        ) : (
          <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
            <DialogBody className="space-y-4">
              <label
                htmlFor="pkg-file"
                className="flex cursor-pointer flex-col items-center gap-2 rounded-xl bg-muted/60 px-4 py-6 text-center text-[13px] text-muted-foreground transition-colors hover:bg-muted focus-within:outline-2 focus-within:outline-ring"
              >
                <FileArchiveIcon className="size-6 text-subtle" aria-hidden />
                {file ? <span className="font-medium text-foreground">{file.name}</span> : <span>Choose a .zip package</span>}
                <input
                  id="pkg-file"
                  type="file"
                  accept=".zip,application/zip"
                  className="sr-only"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </label>
              <Field label="Slug (optional)" htmlFor="pkg-slug" hint="Leave empty to derive it from the package's name.">
                <Input id="pkg-slug" className="font-mono" value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase())} />
              </Field>
              {error && <FieldError>{error}</FieldError>}
            </DialogBody>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={importProblem.isPending}>
                {importProblem.isPending ? "Importing..." : "Import"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
