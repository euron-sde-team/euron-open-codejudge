"use client";

import { Countdown } from "@/components/countdown";
import { usePermissions } from "@/features/auth/api";
import { ContextProblem } from "@/features/shared/context-problem";
import { latePolicyText } from "@/lib/classes";

import { useAssignment, useAssignmentProblem } from "../api";

export function AssignmentProblemScreen({ id, slug }: { id: string; slug: string }) {
  const { signedIn } = usePermissions();
  const a = useAssignment(id);
  const problem = useAssignmentProblem(id, slug);
  const as = a.data;
  const closedReason = !as
    ? null
    : as.status === "closed"
      ? "This assignment is closed: submissions are no longer accepted."
      : as.status === "upcoming"
        ? "This assignment has not opened yet."
        : null;
  return (
    <ContextProblem
      query={problem}
      backHref={`/assignments/${id}`}
      backLabel={as?.title ?? "Assignment"}
      header={
        as && (as.status === "open" || as.status === "late") ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl bg-muted/60 px-4 py-2.5 text-[13px]">
            <span className="font-semibold">{as.title}</span>
            {as.status === "late" ? (
              <span className="text-warning">Past due. {latePolicyText(as.late_policy, as.penalty_percent)}</span>
            ) : (
              <Countdown to={as.my_due_at} label="Due in" className="ml-auto" />
            )}
          </div>
        ) : null
      }
      context="assignment"
      contextId={id}
      signedIn={signedIn}
      closedReason={closedReason}
    />
  );
}
