"use client";

import { ArrowLeftIcon, FileQuestionIcon, RefreshCwIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { toast } from "sonner";

import { CodeEditor } from "@/components/code-editor";
import { CopyButton } from "@/components/copy-button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { usePermissions } from "@/features/auth/api";
import { useLanguages } from "@/features/problems/api";
import { ApiError, errorMessage } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/format";

import { useLiveSubmission, useRejudge } from "../api";
import { ResultPanel } from "./result-panel";

const CONTEXT_LABEL: Record<string, string> = {
  practice: "Practice",
  contest: "Contest",
  assignment: "Assignment",
  assessment: "Assessment",
  reference: "Reference solution",
  run: "Run",
};

export function SubmissionScreen({ id }: { id: string }) {
  const { live, submission, error, refetch } = useLiveSubmission(id);
  const { staff } = usePermissions();
  const languages = useLanguages();
  const rejudge = useRejudge();
  const [latest, setLatest] = React.useState(false);
  if (!submission) {
    return <SubmissionLoading error={error} onRetry={refetch} />;
  }

  const monaco = languages.data?.find((l) => l.id === submission.language)?.monaco ?? "plaintext";
  const languageName = languages.data?.find((l) => l.id === submission.language)?.name ?? submission.language;
  return (
    <div className="space-y-5">
      <Link href="/submissions" className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        All submissions
      </Link>
      <header className="flex flex-wrap items-start gap-3">
        <div className="min-w-0">
          <h1 className="text-[20px] leading-tight font-semibold tracking-[-0.02em]">
            {submission.problem_slug ? (
              <Link href={`/problems/${submission.problem_slug}`} className="hover:underline">
                {submission.problem_title}
              </Link>
            ) : (
              submission.problem_title
            )}
          </h1>
          <p className="mt-1 text-[12.5px] text-muted-foreground">
            {languageName}, {CONTEXT_LABEL[submission.context] ?? submission.context}, submitted {formatDateTime(submission.created_at)}
            {submission.judged_at && `, judged ${formatDateTime(submission.judged_at)}`}
            {submission.worker && staff && ` on ${submission.worker}`}
          </p>
        </div>
        {staff && submission.context !== "run" && (
          <div className="ml-auto flex items-center gap-3">
            <label className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
              <Switch checked={latest} onCheckedChange={setLatest} aria-label="Use the latest tests" />
              Latest tests
            </label>
            <Button
              size="sm"
              variant="secondary"
              disabled={rejudge.isPending || submission.status !== "done"}
              onClick={() =>
                rejudge.mutate(
                  { ids: [submission.id], latest_version: latest },
                  { onSuccess: () => toast.success("Queued for judging again."), onError: (e) => toast.error(errorMessage(e)) },
                )
              }
            >
              <RefreshCwIcon />
              Rejudge
            </Button>
          </div>
        )}
      </header>
      <div className="surface p-4">
        <ResultPanel submission={submission} live={live} showLink={false} />
      </div>
      {submission.source != null && (
        <section className="surface overflow-hidden" aria-label="Source code">
          <div className="flex items-center justify-between bg-muted/50 px-4 py-2">
            <span className="text-[12.5px] font-semibold text-muted-foreground">Source</span>
            <CopyButton value={submission.source} variant="ghost" label="Copy code" />
          </div>
          <CodeEditor value={submission.source} language={monaco} readOnly height={Math.min(640, 60 + submission.source.split("\n").length * 21)} ariaLabel="Submitted code" />
        </section>
      )}
    </div>
  );
}

/** First load: a skeleton, or why the submission cannot be shown. */
function SubmissionLoading({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  if (error instanceof ApiError && error.status === 404) {
    return (
      <EmptyState
        icon={FileQuestionIcon}
        title="This submission is not available"
        description="It may belong to someone else, or the link is mistyped. Your own submissions are always listed."
        action={
          <Link href="/submissions" className={buttonVariants()}>
            My submissions
          </Link>
        }
      />
    );
  }
  if (error) return <ErrorState error={error} title="The submission could not be loaded" onRetry={onRetry} />;
  return (
    <div className="space-y-4">
      <Skeleton className="h-7 w-1/2" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
