"use client";

import { ArrowLeftIcon, ClockIcon, CpuIcon, FileQuestionIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { CopyButton } from "@/components/copy-button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Markdown } from "@/components/markdown";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Workspace } from "@/features/editor/workspace";
import { ApiError } from "@/lib/api/errors";
import type { Problem } from "@/lib/api/types";
import { formatTime } from "@/lib/verdicts";

/**
 * A problem inside a contest, an assignment or an assessment: the statement and samples on
 * the left, the editor on the right, with submissions tagged with the context.
 */
export function ContextProblem({
  query,
  backHref,
  backLabel,
  header,
  context,
  contextId,
  signedIn,
  closedReason,
  onPaste,
  onSubmitted,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; data?: Problem; refetch: () => unknown };
  backHref?: string;
  backLabel?: string;
  header?: React.ReactNode;
  context: "contest" | "assignment" | "assessment";
  contextId: string;
  signedIn: boolean;
  closedReason?: string | null;
  onPaste?: (chars: number) => void;
  onSubmitted?: () => void;
}) {
  if (query.isPending) return <Skeleton className="h-[520px] w-full" />;
  if (query.isError || !query.data) {
    if (query.error instanceof ApiError && (query.error.status === 404 || query.error.status === 403)) {
      return (
        <EmptyState
          icon={FileQuestionIcon}
          title="This problem is not available here"
          description="It may not have opened yet, or you are not part of this. Go back to the list to see what is open."
          action={
            backHref && (
              <Link href={backHref} className={buttonVariants()}>
                {backLabel ?? "Back"}
              </Link>
            )
          }
        />
      );
    }
    return <ErrorState error={query.error} title="The problem could not be loaded" onRetry={() => void query.refetch()} />;
  }
  const p = query.data;
  return (
    <div className="space-y-4">
      {backHref && (
        <Link href={backHref} className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
          <ArrowLeftIcon className="size-4" aria-hidden />
          {backLabel ?? "Back"}
        </Link>
      )}
      {header}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <article className="min-w-0">
          <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.02em]">{p.title}</h1>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <ClockIcon className="size-3.5" aria-hidden />
              {formatTime(p.time_limit_ms)}
            </span>
            <span className="inline-flex items-center gap-1">
              <CpuIcon className="size-3.5" aria-hidden />
              {p.memory_limit_mb} MB
            </span>
          </div>
          {p.statement_md && <Markdown source={p.statement_md} className="mt-5" />}
          {p.samples.map((s, i) => (
            <div key={s.name} className="mt-4 grid gap-3 sm:grid-cols-2">
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
        </article>
        <div className="lg:sticky lg:top-16 lg:self-start">
          <Workspace problem={p} signedIn={signedIn} context={context} contextId={contextId} closedReason={closedReason} onPaste={onPaste} onSubmitted={onSubmitted} />
        </div>
      </div>
    </div>
  );
}
