"use client";

import { CheckCircle2Icon, ClockIcon, CpuIcon, FileQuestionIcon, PencilRulerIcon } from "lucide-react";
import Link from "next/link";

import { CopyButton } from "@/components/copy-button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Hint } from "@/components/hint";
import { Markdown } from "@/components/markdown";
import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { usePermissions } from "@/features/auth/api";
import { Workspace } from "@/features/editor/workspace";
import { ApiError } from "@/lib/api/errors";
import type { Problem } from "@/lib/api/types";
import { DIFFICULTY, formatTime } from "@/lib/verdicts";

import { useProblem } from "../api";

export function ProblemScreen({ slug }: { slug: string }) {
  const q = useProblem(slug);
  const { signedIn, staff } = usePermissions();

  if (q.isPending) {
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-64 w-full" />
        </div>
        <Skeleton className="h-[520px] w-full" />
      </div>
    );
  }
  if (q.isError) {
    if (q.error instanceof ApiError && q.error.status === 404) {
      return (
        <EmptyState
          icon={FileQuestionIcon}
          title="This problem is not available"
          description="It may be a draft, private to a contest or class, or the link is mistyped."
          action={
            <Link href="/problems" className={buttonVariants()}>
              Browse the problems
            </Link>
          }
        />
      );
    }
    return <ErrorState error={q.error} title="The problem could not be loaded" onRetry={() => void q.refetch()} />;
  }

  const p = q.data;
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <article className="min-w-0">
        <ProblemHeader problem={p} staff={staff} />
        {p.statement_md ? (
          <Markdown source={p.statement_md} className="mt-5" />
        ) : (
          <p className="mt-5 text-[13px] text-muted-foreground">This problem has no statement yet.</p>
        )}
        <Samples problem={p} />
        <Groups problem={p} />
      </article>
      <div className="lg:sticky lg:top-16 lg:self-start">
        <Workspace problem={p} signedIn={signedIn} />
      </div>
    </div>
  );
}

function ProblemHeader({ problem: p, staff }: { problem: Problem; staff: boolean }) {
  const d = DIFFICULTY[p.difficulty];
  return (
    <header>
      <div className="flex items-start gap-3">
        <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.02em]">{p.title}</h1>
        {p.mine === "solved" && (
          <span className="mt-1 inline-flex items-center gap-1 text-[12px] font-semibold text-verdict-ac">
            <CheckCircle2Icon className="size-4" aria-hidden />
            Solved
          </span>
        )}
        {staff && (
          <Link href={`/manage/problems/${p.id}`} className={buttonVariants({ variant: "subtle", size: "sm", className: "ml-auto shrink-0" })}>
            <PencilRulerIcon />
            Edit
          </Link>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-[12.5px] text-muted-foreground">
        {d && <span className={`font-semibold ${d.className}`}>{d.label}</span>}
        <span className="inline-flex items-center gap-1">
          <ClockIcon className="size-3.5" aria-hidden />
          {formatTime(p.time_limit_ms)}
          <Hint term="timeLimit" />
        </span>
        <span className="inline-flex items-center gap-1">
          <CpuIcon className="size-3.5" aria-hidden />
          {p.memory_limit_mb} MB
          <Hint term="memoryLimit" />
        </span>
        {p.status === "draft" && <Chip tone="warning">Draft: only staff see it</Chip>}
        {p.tags.map((t) => (
          <Link key={t} href={`/problems?tag=${encodeURIComponent(t)}`} className="rounded-full bg-muted px-2 py-0.5 text-[11.5px] hover:text-foreground">
            {t}
          </Link>
        ))}
      </div>
    </header>
  );
}

function Samples({ problem: p }: { problem: Problem }) {
  if (!p.samples.length) return null;
  return (
    <section className="mt-6 space-y-4" aria-label="Samples">
      {p.samples.map((s, i) => (
        <div key={s.name} className="grid gap-3 sm:grid-cols-2">
          {(["input", "output"] as const).map((part) => (
            <div key={part} className="min-w-0">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-[12px] font-semibold text-muted-foreground">
                  Sample {i + 1} {part}
                </span>
                <CopyButton value={s[part]} iconOnly variant="ghost" label={`Copy sample ${i + 1} ${part}`} />
              </div>
              <pre className="overflow-x-auto rounded-lg bg-code-bg p-3 font-mono text-[12.5px] text-code-fg">{s[part]}</pre>
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}

function Groups({ problem: p }: { problem: Problem }) {
  const scored = p.groups.filter((g) => g.points > 0);
  if (scored.length < 2) return null;
  return (
    <section className="mt-6" aria-label="Scoring">
      <h2 className="flex items-center gap-1.5 text-[14px] font-semibold">
        Scoring
        <Hint term="groups" />
      </h2>
      <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
        {scored.map((g) => (
          <li key={g.name} className="flex justify-between rounded-lg bg-muted/60 px-3 py-2 text-[13px]">
            <span>Group {g.name}</span>
            <span className="tabular font-semibold">{g.points} points</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
