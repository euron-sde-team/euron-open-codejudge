/** Classes and assignments: plain-words rules shown to students and teachers. */
import type { LatePolicy } from "./api/types";

export function latePolicyText(policy: LatePolicy, penaltyPercent: number): string {
  switch (policy) {
    case "accept":
      return "Late work counts in full.";
    case "penalty":
      return penaltyPercent >= 100
        ? "Late work scores nothing."
        : `Late work counts, minus ${penaltyPercent}% of its score.`;
    case "refuse":
      return "Late work is not accepted: submissions close at the due time.";
  }
}

export const STATUS_TEXT: Record<string, string> = {
  upcoming: "Not open yet",
  open: "Open",
  late: "Past due, late work accepted",
  closed: "Closed",
};

/** Where the gradebook CSV downloads from. */
export function gradebookCsvUrl(assignmentId: string): string {
  return `/api/v1/assignments/${encodeURIComponent(assignmentId)}/gradebook.csv`;
}
