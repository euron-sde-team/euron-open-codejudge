"use client";

import { ArrowLeftIcon, CopyCheckIcon, FileQuestionIcon, PlayIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { AdminOnly } from "@/components/admin-only";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Surface, SurfaceHeader } from "@/components/surface";
import { TableSkeleton } from "@/components/table-skeleton";
import { Button, buttonVariants } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { VerdictChip } from "@/components/verdict-chip";
import { LanguageName } from "@/components/language-name";
import { usePermissions } from "@/features/auth/api";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { PlagiarismPairDetail, PlagiarismRun, PlagiarismScope } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatDateTime, formatRelative } from "@/lib/format";
import { highlightedLines, similarityLabel, similarityTone } from "@/lib/plagiarism";

import { usePair, useRun, useRuns, useStartRun } from "../api";

const SCOPE_LABEL: Record<PlagiarismScope, string> = { problem: "Problem", contest: "Contest", assignment: "Assignment" };
const RUN_STATUS: Record<string, { label: string; tone: "neutral" | "info" | "success" | "danger" }> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Comparing", tone: "info" },
  done: { label: "Done", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

export function PlagiarismScreen() {
  const { user, staff } = usePermissions();
  const router = useRouter();
  const runs = useRuns();
  const start = useStartRun();
  const [scope, setScope] = React.useState<PlagiarismScope>("problem");
  const [scopeId, setScopeId] = React.useState("");
  const [threshold, setThreshold] = React.useState("50");
  const [error, setError] = React.useState<string | null>(null);
  if (user && !staff) return <AdminOnly what="Plagiarism checks" />;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = Number(threshold) / 100;
    if (!scopeId.trim()) return setError(scope === "problem" ? "Enter the problem's slug." : `Enter the ${scope}'s id (from its address).`);
    if (!Number.isFinite(t) || t < 0.1 || t > 1) return setError("The threshold must be between 10 and 100 percent.");
    setError(null);
    start.mutate(
      { scope, scope_id: scopeId.trim(), threshold: t },
      {
        onSuccess: (r) => {
          toast.success("Check started. Results appear when the comparison finishes.");
          router.push(`/plagiarism/runs/${r.id}`);
        },
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }

  return (
    <>
      <PageHeader
        title="Plagiarism"
        description="Compare submissions to the same problem for structural similarity. Renamed variables and reordered functions still match; a match is a reason to look, not proof."
      />
      <Surface className="mb-5">
        <SurfaceHeader title="Start a check" description="Each person's latest accepted submission per problem (else their best scoring one) is compared with everyone else's in the same language." />
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3 px-5 pb-5" noValidate>
          <Field label="Compare within" htmlFor="pl-scope" className="w-40">
            <SimpleSelect
              id="pl-scope"
              value={scope}
              onValueChange={(v) => setScope((v || "problem") as PlagiarismScope)}
              options={(Object.keys(SCOPE_LABEL) as PlagiarismScope[]).map((s) => ({ value: s, label: SCOPE_LABEL[s] }))}
            />
          </Field>
          <Field label={scope === "problem" ? "Problem slug" : `${SCOPE_LABEL[scope]} id`} htmlFor="pl-id" className="min-w-56 flex-1">
            <Input id="pl-id" className="font-mono" value={scopeId} onChange={(e) => setScopeId(e.target.value)} />
          </Field>
          <Field label="Flag at (similarity %)" htmlFor="pl-th" className="w-36">
            <Input id="pl-th" inputMode="numeric" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
          </Field>
          <Button type="submit" disabled={start.isPending}>
            <PlayIcon />
            {start.isPending ? "Starting..." : "Start check"}
          </Button>
          {error && <FieldError className="w-full">{error}</FieldError>}
        </form>
      </Surface>
      <div className="surface overflow-x-auto">
        {runs.isPending ? (
          <TableSkeleton rows={4} cols={5} />
        ) : runs.isError ? (
          <ErrorState error={runs.error} title="Checks could not be loaded" onRetry={() => void runs.refetch()} />
        ) : !runs.data.length ? (
          <EmptyState icon={CopyCheckIcon} title="No checks yet" description="Start one above for a problem, a contest or an assignment. Pairs above the threshold are listed for review." />
        ) : (
          <table className="w-full min-w-[600px] text-[13px]">
            <thead>
              <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
                <th className="px-4 py-2.5 font-semibold">Started</th>
                <th className="px-3 py-2.5 font-semibold">Scope</th>
                <th className="px-3 py-2.5 font-semibold">Status</th>
                <th className="px-3 py-2.5 text-right font-semibold">Programs</th>
                <th className="px-3 py-2.5 text-right font-semibold">Flagged pairs</th>
              </tr>
            </thead>
            <tbody>
              {runs.data.map((r) => (
                <RunRow key={r.id} r={r} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function RunRow({ r }: { r: PlagiarismRun }) {
  const st = RUN_STATUS[r.status] ?? { label: r.status, tone: "neutral" as const };
  return (
    <tr className="border-t border-hairline hover:bg-muted/40">
      <td className="px-4 py-2.5">
        <Link href={`/plagiarism/runs/${r.id}`} className="font-medium text-primary hover:underline">
          {formatRelative(r.created_at)}
        </Link>
      </td>
      <td className="px-3 py-2.5">
        {SCOPE_LABEL[r.scope]}{" "}
        {r.scope_title ? <span className="text-foreground">{r.scope_title}</span> : <span className="font-mono text-[11.5px] text-faint">{r.scope_id.slice(0, 8)}</span>}
      </td>
      <td className="px-3 py-2.5">
        <Chip tone={st.tone}>{st.label}</Chip>
      </td>
      <td className="tabular px-3 py-2.5 text-right">{r.documents}</td>
      <td className={cn("tabular px-3 py-2.5 text-right font-semibold", r.flagged > 0 && "text-warning")}>{r.status === "done" ? r.flagged : ""}</td>
    </tr>
  );
}

export function RunScreen({ id }: { id: string }) {
  const run = useRun(id);
  if (run.isPending) return <Skeleton className="h-64 w-full" />;
  if (run.isError) {
    if (run.error instanceof ApiError && run.error.status === 404)
      return (
        <EmptyState
          icon={FileQuestionIcon}
          title="This check does not exist"
          description="It may have been removed."
          action={
            <Link href="/plagiarism" className={buttonVariants()}>
              All checks
            </Link>
          }
        />
      );
    return <ErrorState error={run.error} title="The check could not be loaded" onRetry={() => void run.refetch()} />;
  }
  const r = run.data;
  const st = RUN_STATUS[r.status] ?? { label: r.status, tone: "neutral" as const };
  return (
    <div className="space-y-5">
      <Link href="/plagiarism" className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        Plagiarism
      </Link>
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-[22px] font-semibold tracking-[-0.02em]">
          {r.scope_title ?? `${SCOPE_LABEL[r.scope]} check`}, {formatDateTime(r.created_at)}
        </h1>
        <Chip tone={st.tone}>{st.label}</Chip>
      </header>
      <p className="text-[13px] text-muted-foreground">
        {r.documents} programs, {r.comparisons} comparisons, flagged at {similarityLabel(r.threshold)} similarity or more.
        {r.status === "running" || r.status === "queued" ? " This page refreshes until it finishes." : ""}
      </p>
      {r.error && <p className="rounded-lg bg-danger-soft px-3.5 py-2.5 text-[13px] text-danger">{r.error}</p>}
      {r.status === "done" &&
        (!r.pairs.length ? (
          <div className="surface">
            <EmptyState icon={CopyCheckIcon} title="Nothing above the threshold" description="No two programs are this similar. Lower the threshold and start a new check to see weaker matches." />
          </div>
        ) : (
          <ul className="surface divide-y divide-hairline overflow-hidden">
            {r.pairs.map((p) => (
              <li key={p.id}>
                <Link href={`/plagiarism/pairs/${p.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-muted/50 sm:px-5">
                  <Chip tone={similarityTone(p.similarity)}>{similarityLabel(p.similarity)}</Chip>
                  <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium">
                    {p.a.author} and {p.b.author}
                  </span>
                  <span className="text-[12.5px] text-muted-foreground">
                    {p.problem_title}, <LanguageName id={p.language} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ))}
    </div>
  );
}

export function PairScreen({ id }: { id: string }) {
  const pair = usePair(id);
  if (pair.isPending) return <Skeleton className="h-96 w-full" />;
  if (pair.isError) return <ErrorState error={pair.error} title="The pair could not be loaded" onRetry={() => void pair.refetch()} />;
  const p = pair.data;
  return (
    <div className="space-y-5">
      <button type="button" onClick={() => history.back()} className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        Back to the check
      </button>
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-[20px] font-semibold tracking-[-0.02em]">
          {p.a.author} and {p.b.author}
        </h1>
        <Chip tone={similarityTone(p.similarity)}>{similarityLabel(p.similarity)} similar</Chip>
        <span className="text-[13px] text-muted-foreground">
          {p.problem_title}, <LanguageName id={p.language} />
        </span>
      </header>
      <p className="rounded-lg bg-info-soft px-3.5 py-2.5 text-[12.5px] text-info">
        Highlighted lines are the parts that match structurally. Short or standard solutions can look alike by chance: talk to the people before drawing a conclusion.
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <SourcePane side={p.a} source={p.source_a} />
        <SourcePane side={p.b} source={p.source_b} />
      </div>
    </div>
  );
}

function SourcePane({ side, source }: { side: PlagiarismPairDetail["a"]; source: string }) {
  const lines = source.split("\n");
  const marked = highlightedLines(side.ranges, lines.length);
  return (
    <section className="surface min-w-0 overflow-hidden" aria-label={`${side.author}'s program`}>
      <div className="flex flex-wrap items-center gap-2 bg-muted/50 px-4 py-2 text-[12.5px]">
        <span className="font-semibold">{side.author}</span>
        <VerdictChip verdict={side.verdict} />
        <span className="text-muted-foreground">{similarityLabel(side.coverage)} of it matched</span>
        <Link href={`/submissions/${side.submission_id}`} className="ml-auto font-medium text-primary hover:underline">
          Submission
        </Link>
      </div>
      <pre className="max-h-[640px] overflow-auto bg-code-bg py-2 font-mono text-[12px] leading-[1.6] text-code-fg">
        {lines.map((line, i) => (
          <div key={i} className={cn("flex px-2", marked.has(i + 1) && "bg-[color-mix(in_srgb,var(--warning)_28%,transparent)]")}>
            <span className="w-10 shrink-0 pr-3 text-right text-code-muted select-none">{i + 1}</span>
            <span className="whitespace-pre">{line || " "}</span>
          </div>
        ))}
      </pre>
    </section>
  );
}
