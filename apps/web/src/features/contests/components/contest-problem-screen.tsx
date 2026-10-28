"use client";

import { Countdown } from "@/components/countdown";
import { usePermissions } from "@/features/auth/api";
import { ContextProblem } from "@/features/shared/context-problem";

import { useContest, useContestProblem, useMyContestStatus } from "../api";

export function ContestProblemScreen({ slug, label }: { slug: string; label: string }) {
  const { signedIn, staff } = usePermissions();
  const contest = useContest(slug);
  const status = useMyContestStatus(slug, signedIn);
  const problem = useContestProblem(slug, label);
  const c = contest.data;
  const registered = status.data?.registered ?? c?.registered ?? false;
  const closedReason = !c
    ? null
    : c.phase === "ended"
      ? "The contest has ended: submissions are closed. Practise the problem from the problem list if it is public."
      : c.phase === "upcoming"
        ? "The contest has not started yet."
        : !registered && !staff
          ? "Register for the contest to submit."
          : null;

  return (
    <ContextProblem
      query={problem}
      backHref={`/contests/${slug}`}
      backLabel={c?.title ?? "Contest"}
      header={
        c && c.phase === "running" ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl bg-muted/60 px-4 py-2.5 text-[13px]">
            <span className="font-semibold">
              Problem {label} of {c.title}
            </span>
            <Countdown to={c.ends_at} label="Ends in" className="ml-auto" />
          </div>
        ) : null
      }
      context="contest"
      contextId={c?.id ?? ""}
      signedIn={signedIn}
      closedReason={closedReason}
    />
  );
}
