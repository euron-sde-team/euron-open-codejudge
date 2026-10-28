"use client";

import { LoaderCircleIcon } from "lucide-react";
import Link from "next/link";

import { VerdictChip } from "@/components/verdict-chip";
import type { Submission } from "@/lib/api/types";
import { progressLabel, type LiveEvent } from "@/lib/live";
import { formatMemory, formatScore, formatTime } from "@/lib/verdicts";

import { TestsTable } from "./tests-table";

/** The outcome of a run or a submission: progress while judging, then the full result. */
export function ResultPanel({ submission, live, showLink = true }: { submission: Submission | undefined; live: LiveEvent | null; showLink?: boolean }) {
  if (!submission) return null;
  const done = submission.status === "done";
  if (!done) {
    const event = live ?? { status: submission.status, progress: submission.progress };
    return (
      <div className="flex items-center gap-3 rounded-xl bg-info-soft px-4 py-3 text-[13px] text-info" role="status" aria-live="polite">
        <LoaderCircleIcon className="size-4 animate-spin" aria-hidden />
        <span className="font-medium">{progressLabel(event as LiveEvent)}</span>
        <span className="text-info/70">{submission.context === "run" ? "Running your code" : "Judging your submission"}</span>
      </div>
    );
  }

  const isRun = submission.context === "run";
  const custom = isRun && submission.run_input != null;
  return (
    <div className="space-y-3" aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl bg-muted/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <VerdictChip verdict={submission.verdict} long />
          {submission.late && <span className="text-[12px] font-medium text-warning">Late</span>}
        </div>
        {!custom && submission.max_score > 0 && (
          <Figure label={isRun ? "Samples" : "Score"} value={isRun ? undefined : formatScore(submission.score, submission.max_score)} />
        )}
        {submission.verdict !== "CE" && (
          <>
            <Figure label="Time" value={formatTime(submission.time_ms)} />
            <Figure label="Memory" value={formatMemory(submission.memory_kb)} />
          </>
        )}
        {showLink && !isRun && (
          <Link href={`/submissions/${submission.id}`} className="ml-auto text-[12.5px] font-medium text-primary hover:underline">
            Open submission
          </Link>
        )}
      </div>
      <p className="text-[12.5px] text-muted-foreground">{explain(submission)}</p>
      {submission.compile_output && (
        <div>
          <div className="mb-1 text-[12px] font-semibold text-muted-foreground">Compiler output</div>
          <pre className="max-h-64 overflow-auto rounded-lg bg-code-bg p-3 font-mono text-[12px] whitespace-pre-wrap text-code-fg">{submission.compile_output}</pre>
        </div>
      )}
      {custom && (
        <div>
          <div className="mb-1 text-[12px] font-semibold text-muted-foreground">Output</div>
          <pre className="max-h-64 overflow-auto rounded-lg bg-code-bg p-3 font-mono text-[12px] text-code-fg">{submission.run_output || "(no output)"}</pre>
        </div>
      )}
      {submission.error && <p className="rounded-lg bg-warning-soft px-3 py-2 text-[12.5px] text-warning">Judge error (staff only): {submission.error}</p>}
      <TestsTable tests={submission.tests ?? []} groups={submission.groups} />
    </div>
  );
}

function Figure({ label, value }: { label: string; value?: string }) {
  if (value === undefined) return null;
  return (
    <div className="flex items-baseline gap-1.5 text-[13px]">
      <span className="text-muted-foreground">{label}</span>
      <span className="tabular font-semibold">{value}</span>
    </div>
  );
}

/** One sentence on what to do next. */
export function explain(s: Submission): string {
  const isRun = s.context === "run";
  switch (s.verdict) {
    case "AC":
      return isRun
        ? s.run_input != null
          ? "Your program ran without errors on your input. Compare the output with what you expect."
          : "Your program passes the samples. Submit it to be judged on the hidden tests."
        : "Every test passed. Well done.";
    case "WA":
      return isRun
        ? "The output differs from the expected answer. Open the sample to compare."
        : "One of the tests got a different answer. Check edge cases: the smallest and largest inputs, duplicates, empty input.";
    case "TLE":
      return "Too slow for the time limit. Look for a faster algorithm or reduce repeated work; reading input in bulk also helps.";
    case "MLE":
      return "Uses more memory than allowed. Avoid storing everything at once, or use more compact data structures.";
    case "RE":
      return "The program crashed. Common causes: an index out of range, division by zero, deep recursion, or an uncaught exception.";
    case "OLE":
      return "The program printed far more than expected. Check for a loop that never stops printing.";
    case "CE":
      return "The code did not compile. The compiler output below points at the line.";
    case "IE":
      return "The judge failed, not your program. It is retried automatically; if it stays like this, tell a staff member.";
    default:
      return "";
  }
}
