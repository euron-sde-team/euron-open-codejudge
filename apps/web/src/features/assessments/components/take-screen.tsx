"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2Icon, ClockIcon, FlagIcon, LockKeyholeIcon, TimerOffIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { BrandMark } from "@/components/brand";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Countdown } from "@/components/countdown";
import { Markdown } from "@/components/markdown";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { VerdictChip } from "@/components/verdict-chip";
import { Workspace } from "@/features/editor/workspace";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { CandidateView } from "@/lib/api/types";
import { getCandidateToken } from "@/lib/candidate";
import { cn } from "@/lib/cn";
import { formatScore, formatTime } from "@/lib/verdicts";

import { openCandidateSession, recordCandidateEvent, useCandidateFinish, useCandidateView } from "../api";

/** The candidate's whole experience: no app navigation, nothing outside the assessment. */
export function TakeScreen() {
  const [token, setToken] = React.useState<string | null | undefined>(undefined);
  React.useEffect(() => setToken(getCandidateToken()), []);
  const view = useCandidateView(!!token);
  const client = useQueryClient();
  const [starting, setStarting] = React.useState(false);
  const [startError, setStartError] = React.useState<string | null>(null);

  async function start() {
    if (!token) return;
    setStarting(true);
    setStartError(null);
    try {
      const v = await openCandidateSession(token);
      client.setQueryData(["candidate", "view"], v);
    } catch (e) {
      setStartError(errorMessage(e));
    } finally {
      setStarting(false);
    }
  }

  let body: React.ReactNode;
  if (token === undefined) body = <Skeleton className="mx-auto mt-16 h-48 w-full max-w-xl" />;
  else if (!token)
    body = (
      <Closing
        icon={LockKeyholeIcon}
        title="Open your invitation link"
        text="This page works from the personal link in your invitation email. Open that link in this browser to continue."
      />
    );
  else if (view.isPending) body = <Skeleton className="mx-auto mt-16 h-48 w-full max-w-xl" />;
  else if (view.isError) {
    const err = view.error;
    if (err instanceof ApiError && err.code === "not_started") body = <BeforeStart onStart={() => void start()} starting={starting} error={startError} />;
    else
      body = (
        <Closing
          icon={TimerOffIcon}
          title="This link can no longer be used"
          text={`${errorMessage(err)} If you think this is a mistake, reply to your invitation email.`}
        />
      );
  } else {
    const v = view.data;
    if (v.status === "submitted")
      body = <Closing icon={CheckCircle2Icon} title="Submitted. Thank you." text="Your answers are with the interviewers. You can close this tab now." />;
    else if (v.status === "expired")
      body = <Closing icon={TimerOffIcon} title="Time is up" text="The assessment has ended. Everything you submitted before the deadline counts. You can close this tab now." />;
    else if (v.status === "revoked") body = <Closing icon={LockKeyholeIcon} title="This invitation was withdrawn" text="Reply to your invitation email if you have questions." />;
    else if (v.status === "invited") body = <BeforeStart onStart={() => void start()} starting={starting} error={startError} />;
    else body = <Exam view={v} onElapsed={() => void view.refetch()} />;
  }

  return (
    <div className="min-h-dvh bg-background">
      <header className="flex h-14 items-center gap-2 px-4 sm:px-6">
        <BrandMark className="size-6" />
        <span className="text-[14px] font-semibold">CodeJudge assessment</span>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1400px] px-4 pb-16 sm:px-6">{body}</main>
    </div>
  );
}

function Closing({ icon: Icon, title, text }: { icon: typeof ClockIcon; title: string; text: string }) {
  return (
    <div className="surface mx-auto mt-16 max-w-xl px-8 py-10 text-center" role="status">
      <div className="mx-auto mb-4 flex size-11 items-center justify-center rounded-xl bg-primary-soft text-primary">
        <Icon className="size-5" />
      </div>
      <h1 className="text-lg font-semibold">{title}</h1>
      <p className="mt-2 text-[13.5px] text-muted-foreground">{text}</p>
    </div>
  );
}

function BeforeStart({ onStart, starting, error }: { onStart: () => void; starting: boolean; error: string | null }) {
  return (
    <div className="surface mx-auto mt-12 max-w-xl space-y-4 px-8 py-8">
      <h1 className="text-xl font-semibold">Before you start</h1>
      <ul className="list-disc space-y-1.5 pl-5 text-[13.5px] text-muted-foreground">
        <li>This is a timed coding assessment. The clock starts when you press Start and does not pause.</li>
        <li>Solve the problems in the browser. Run your code on the samples as often as you like; submit when you are ready. Your best submission per problem counts.</li>
        <li>Keep this tab open. Pastes and switching away from the tab are recorded and shown to the interviewers as signals, not as proof of anything.</li>
        <li>When you are done, press Finish. If time runs out, what you submitted counts.</li>
      </ul>
      {error && (
        <p className="rounded-lg bg-danger-soft px-3.5 py-2.5 text-[13px] text-danger" role="alert">
          {error}
        </p>
      )}
      <Button size="lg" className="w-full" disabled={starting} onClick={onStart}>
        <ClockIcon />
        {starting ? "Starting..." : "Start the assessment"}
      </Button>
    </div>
  );
}

function Exam({ view: v, onElapsed }: { view: CandidateView; onElapsed: () => void }) {
  const finish = useCandidateFinish();
  const client = useQueryClient();
  // Scores update once a submission is judged: look again shortly after submitting.
  const refreshSoon = React.useCallback(() => {
    for (const ms of [4000, 12000]) setTimeout(() => void client.invalidateQueries({ queryKey: ["candidate", "view"] }), ms);
  }, [client]);
  const [index, setIndex] = React.useState(0);
  const [confirming, setConfirming] = React.useState(false);
  // The server says how many seconds are left; count down from that, not the local clock.
  const deadline = React.useMemo(() => new Date(Date.now() + v.seconds_left * 1000), [v.seconds_left]);
  const current = v.problems[index] ?? v.problems[0];

  React.useEffect(() => {
    const onVisibility = () => void recordCandidateEvent(document.visibilityState === "hidden" ? "tab_hidden" : "tab_visible");
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  const total = v.problems.reduce((s, p) => s + (p.best_score ?? 0), 0);

  return (
    <div className="space-y-4">
      <div className="surface flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold">{v.title}</div>
          <div className="text-[12px] text-muted-foreground">{v.name ? `Good luck, ${v.name.split(" ")[0]}.` : "Good luck."}</div>
        </div>
        <span className="tabular text-[13px] text-muted-foreground">Score so far {formatScore(total, v.total_points)}</span>
        <Countdown to={deadline} label="Time left" onElapsed={onElapsed} className="ml-auto text-[18px]" />
        <Button variant="secondary" onClick={() => setConfirming(true)}>
          <FlagIcon />
          Finish
        </Button>
      </div>
      {v.instructions_md && index === 0 && (
        <details className="surface px-4 py-3" open>
          <summary className="cursor-pointer text-[13px] font-semibold">Instructions</summary>
          <Markdown source={v.instructions_md} className="mt-2 text-[13.5px]" />
        </details>
      )}
      <nav aria-label="Problems" className="flex flex-wrap gap-2">
        {v.problems.map((p, i) => (
          <button
            key={p.problem.id}
            type="button"
            onClick={() => setIndex(i)}
            aria-current={i === index ? "page" : undefined}
            className={cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
              i === index ? "bg-card shadow-[var(--elev-1)]" : "bg-muted/60 text-muted-foreground hover:text-foreground",
            )}
          >
            {i + 1}. {p.problem.title}
            {p.best_verdict && <VerdictChip verdict={p.best_verdict} />}
            <span className="tabular text-[12px] text-muted-foreground">{formatScore(p.best_score ?? 0, p.points)}</span>
          </button>
        ))}
      </nav>
      {current && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <article className="min-w-0">
            <h2 className="text-[20px] font-semibold">{current.problem.title}</h2>
            <p className="mt-1 text-[12.5px] text-muted-foreground">
              {formatTime(current.problem.time_limit_ms)}, {current.problem.memory_limit_mb} MB, {current.points} points
            </p>
            {current.problem.statement_md && <Markdown source={current.problem.statement_md} className="mt-4" />}
            {current.problem.samples.map((s, i) => (
              <div key={s.name} className="mt-4 grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="mb-1 text-[12px] font-semibold text-muted-foreground">Sample {i + 1} input</div>
                  <pre className="overflow-x-auto rounded-lg bg-code-bg p-3 font-mono text-[12.5px] text-code-fg">{s.input}</pre>
                </div>
                <div>
                  <div className="mb-1 text-[12px] font-semibold text-muted-foreground">Sample {i + 1} output</div>
                  <pre className="overflow-x-auto rounded-lg bg-code-bg p-3 font-mono text-[12.5px] text-code-fg">{s.output}</pre>
                </div>
              </div>
            ))}
          </article>
          <div className="lg:sticky lg:top-4 lg:self-start">
            <Workspace
              key={current.problem.id}
              problem={current.problem}
              signedIn
              context="assessment"
              contextId={v.invitation_id}
              hints={false}
              onSubmitted={refreshSoon}
              onPaste={(chars) => void recordCandidateEvent("paste", { chars, problem: current.problem.slug })}
            />
          </div>
        </div>
      )}
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Finish the assessment?"
        description="You cannot submit anything after this. Your best submission per problem counts."
        confirmLabel="Finish now"
        pending={finish.isPending}
        onConfirm={() =>
          finish.mutate(undefined, {
            onSuccess: () => setConfirming(false),
            onError: (e) => {
              setConfirming(false);
              toast.error(errorMessage(e));
            },
          })
        }
      />
    </div>
  );
}
