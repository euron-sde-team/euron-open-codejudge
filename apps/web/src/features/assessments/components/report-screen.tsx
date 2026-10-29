"use client";

import { ArrowLeftIcon, ClipboardPasteIcon, EyeIcon, EyeOffIcon, FileQuestionIcon, SendIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { CodeEditor } from "@/components/code-editor";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Stat } from "@/components/stat";
import { Surface, SurfaceHeader } from "@/components/surface";
import { buttonVariants } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { VerdictChip } from "@/components/verdict-chip";
import { useLanguages } from "@/features/problems/api";
import { ApiError } from "@/lib/api/errors";
import type { CandidateReport } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import { formatMemory, formatScore, formatTime } from "@/lib/verdicts";

import { useReport } from "../api";
import { INVITATION_STATUS } from "./assessment-screen";

type TimelineItem =
  | { kind: "submission"; at: string; sub: CandidateReport["submissions"][number] }
  | { kind: "event"; at: string; event: CandidateReport["events"][number] };

/** Submissions and recorded events merged in time order. */
export function timeline(report: Pick<CandidateReport, "submissions" | "events">): TimelineItem[] {
  const items: TimelineItem[] = [
    ...report.submissions.map((sub) => ({ kind: "submission" as const, at: sub.created_at, sub })),
    ...report.events.map((event) => ({ kind: "event" as const, at: event.at, event })),
  ];
  return items.sort((a, b) => a.at.localeCompare(b.at));
}

const EVENT_TEXT: Record<string, { label: string; icon: typeof EyeIcon }> = {
  started: { label: "Started the assessment", icon: EyeIcon },
  submitted: { label: "Finished the assessment", icon: EyeIcon },
  paste: { label: "Pasted into the editor", icon: ClipboardPasteIcon },
  tab_hidden: { label: "Left the tab", icon: EyeOffIcon },
  tab_visible: { label: "Came back to the tab", icon: EyeIcon },
};

export function ReportScreen({ assessmentId, invitationId }: { assessmentId: string; invitationId: string }) {
  const report = useReport(assessmentId, invitationId);
  const languages = useLanguages();
  const [open, setOpen] = React.useState<string | null>(null);

  if (report.isPending) return <Skeleton className="h-96 w-full" />;
  if (report.isError) {
    if (report.error instanceof ApiError && report.error.status === 404) {
      return (
        <EmptyState
          icon={FileQuestionIcon}
          title="No report for this candidate"
          description="The invitation may have been deleted."
          action={
            <Link href={`/assessments/${assessmentId}`} className={buttonVariants()}>
              Back to the assessment
            </Link>
          }
        />
      );
    }
    return <ErrorState error={report.error} title="The report could not be loaded" onRetry={() => void report.refetch()} />;
  }
  const r = report.data;
  const inv = r.invitation;
  const st = INVITATION_STATUS[inv.status] ?? { label: inv.status, tone: "neutral" as const };
  const items = timeline(r);
  const signals = r.events.filter((e) => e.kind === "paste" || e.kind === "tab_hidden").length;

  return (
    <div className="space-y-5">
      <Link href={`/assessments/${assessmentId}`} className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        {r.assessment_title}
      </Link>
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.02em]">{inv.name || inv.email}</h1>
        <Chip tone={st.tone}>{st.label}</Chip>
        {inv.name && <span className="text-[13px] text-muted-foreground">{inv.email}</span>}
      </header>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Score" value={formatScore(r.total, r.total_points)} tone={r.total >= r.total_points ? "good" : "default"} />
        <Stat label="Time used" value={r.minutes_used == null ? "n/a" : r.minutes_used < 1 ? `Under 1 of ${r.duration_minutes} min` : `${Math.round(r.minutes_used)} of ${r.duration_minutes} min`} />
        <Stat label="Submissions" value={r.submissions.length} />
        <Stat label="Signals" value={signals} detail="Pastes and tab switches" />
      </div>

      <Surface>
        <SurfaceHeader title="Problems" />
        <ul className="divide-y divide-hairline px-5 pb-3">
          {r.problems.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-3 py-2.5 text-[13px]">
              <span className="min-w-0 flex-1 font-medium">{p.title}</span>
              {p.best_verdict && <VerdictChip verdict={p.best_verdict} />}
              <span className="text-muted-foreground">
                {p.attempts} attempt{p.attempts === 1 ? "" : "s"}
              </span>
              <span className="tabular w-24 text-right font-semibold">{formatScore(p.earned, p.points)}</span>
            </li>
          ))}
        </ul>
      </Surface>

      <Surface>
        <SurfaceHeader title="Timeline" description="Every submission (open one to read the code) and every recorded signal, in time order." />
        <div className="mx-5 mb-4 rounded-lg bg-info-soft px-3.5 py-2.5 text-[12.5px] text-info">{r.signals_note}</div>
        {!items.length ? (
          <p className="px-5 pb-5 text-[13px] text-muted-foreground">Nothing recorded yet.</p>
        ) : (
          <ol className="space-y-1 px-5 pb-5">
            {items.map((item, i) =>
              item.kind === "submission" ? (
                <li key={`s-${item.sub.id}`} className="rounded-lg bg-muted/40">
                  <button
                    type="button"
                    onClick={() => setOpen(open === item.sub.id ? null : item.sub.id)}
                    aria-expanded={open === item.sub.id}
                    className="flex w-full flex-wrap items-center gap-3 px-3 py-2 text-left text-[13px] focus-visible:outline-2 focus-visible:outline-ring"
                  >
                    <span className="w-28 text-[12px] text-muted-foreground">{formatDateTime(item.at)}</span>
                    <SendIcon className="size-3.5 text-subtle" aria-hidden />
                    <span className="font-medium">{r.problems.find((p) => p.id === item.sub.problem_id)?.title ?? item.sub.problem_slug}</span>
                    <span className="text-muted-foreground">{languages.data?.find((l) => l.id === item.sub.language)?.name ?? item.sub.language}</span>
                    <VerdictChip verdict={item.sub.verdict} />
                    <span className="tabular ml-auto text-muted-foreground">
                      {formatScore(item.sub.score, item.sub.max_score)}, {formatTime(item.sub.time_ms)}, {formatMemory(item.sub.memory_kb)}
                    </span>
                  </button>
                  {open === item.sub.id && (
                    <div className="overflow-hidden rounded-b-lg">
                      <CodeEditor
                        value={item.sub.source}
                        readOnly
                        language={languages.data?.find((l) => l.id === item.sub.language)?.monaco ?? "plaintext"}
                        height={Math.min(520, 60 + item.sub.source.split("\n").length * 21)}
                        ariaLabel="Submitted code"
                      />
                    </div>
                  )}
                </li>
              ) : (
                <li key={`e-${i}`} className={cn("flex flex-wrap items-center gap-3 px-3 py-1.5 text-[13px]", item.event.kind === "paste" || item.event.kind === "tab_hidden" ? "text-warning" : "text-muted-foreground")}>
                  <span className="w-28 text-[12px] text-muted-foreground">{formatDateTime(item.at)}</span>
                  {React.createElement(EVENT_TEXT[item.event.kind]?.icon ?? EyeIcon, { className: "size-3.5", "aria-hidden": true })}
                  <span>{EVENT_TEXT[item.event.kind]?.label ?? item.event.kind}</span>
                  {item.event.kind === "paste" && typeof item.event.detail.chars === "number" && <span className="text-muted-foreground">{item.event.detail.chars} characters</span>}
                </li>
              ),
            )}
          </ol>
        )}
      </Surface>
    </div>
  );
}
