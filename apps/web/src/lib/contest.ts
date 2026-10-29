/** Scoreboard and contest presentation rules, kept pure so they are tested once. */
import type { ContestFormat, Scoreboard, ScoreCell } from "./api/types";

export interface CellView {
  /** The main text: "+", "+2", "-3", "?", or an IOI score. */
  text: string;
  /** The second line: the solve minute (ICPC) or nothing. */
  sub: string | null;
  tone: "solved" | "first" | "failed" | "pending" | "partial" | "empty";
  /** For screen readers. */
  label: string;
}

/**
 * ICPC: "+" when solved first try, "+n" after n wrong tries, "-n" for n wrong tries with
 * no solve, "?" while something is pending (frozen or judging). IOI: the best score.
 */
export function cellView(format: ContestFormat, cell: ScoreCell | undefined, points = 100): CellView {
  // ICPC cells count only the rejected tries before the first accept (a first-try solve has
  // attempts 0); IOI cells count every submission.
  if (!cell || (!cell.solved && cell.attempts === 0 && cell.pending === 0)) return { text: "", sub: null, tone: "empty", label: "No attempt" };
  if (format === "ioi") {
    const score = Math.round(cell.score * 100) / 100;
    const tone = cell.pending > 0 && score === 0 ? "pending" : score >= points ? "solved" : score > 0 ? "partial" : "failed";
    return {
      text: cell.pending > 0 && score === 0 ? "?" : String(score),
      sub: cell.pending > 0 ? `${cell.pending} pending` : null,
      tone,
      label: `${score} points after ${cell.attempts} attempt${cell.attempts === 1 ? "" : "s"}${cell.pending ? `, ${cell.pending} pending` : ""}`,
    };
  }
  if (cell.solved) {
    const wrong = cell.attempts;
    return {
      text: wrong > 0 ? `+${wrong}` : "+",
      sub: cell.minute != null ? `${cell.minute}'` : null,
      tone: cell.first ? "first" : "solved",
      label: `Solved at minute ${cell.minute ?? "?"} after ${wrong} wrong tr${wrong === 1 ? "y" : "ies"}${cell.first ? ", first to solve" : ""}`,
    };
  }
  if (cell.pending > 0) {
    return { text: cell.attempts ? `?${cell.attempts}` : "?", sub: null, tone: "pending", label: `${cell.attempts} wrong, ${cell.pending} pending` };
  }
  return { text: `-${cell.attempts}`, sub: null, tone: "failed", label: `${cell.attempts} wrong tr${cell.attempts === 1 ? "y" : "ies"}, not solved` };
}

export interface FreezeBanner {
  tone: "info" | "warning";
  text: string;
}

/**
 * What to say about the freeze. Contestants see "frozen" once the view hides results;
 * staff see that the public board is frozen while they still see everything.
 */
export function freezeBanner(board: Pick<Scoreboard, "frozen" | "freeze_at" | "phase">, staff: boolean, now: Date = new Date()): FreezeBanner | null {
  if (!board.freeze_at) return null;
  const freezeAt = new Date(board.freeze_at);
  if (board.frozen) {
    return {
      tone: "warning",
      text:
        board.phase === "ended"
          ? "The scoreboard is frozen: results after the freeze are hidden until staff reveal them. Submissions after it show as pending."
          : "The scoreboard is frozen: other people's results after the freeze show as pending. Your own verdicts are always shown.",
    };
  }
  if (staff && now >= freezeAt && board.phase !== "upcoming") {
    return { tone: "info", text: "Contestants see a frozen scoreboard. You see every result. Unfreeze to reveal them to everyone." };
  }
  if (now < freezeAt && board.phase === "running") {
    return { tone: "info", text: `The scoreboard freezes at ${freezeAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.` };
  }
  return null;
}

export const FORMAT_LABEL: Record<ContestFormat, string> = {
  icpc: "ICPC: problems solved, then least penalty time",
  ioi: "IOI: points per problem, partial scores count",
};

/** Next free problem label after the used ones: A, B, ... Z. */
export function nextLabel(used: string[]): string {
  for (let i = 0; i < 26; i += 1) {
    const l = String.fromCharCode(65 + i);
    if (!used.includes(l)) return l;
  }
  return "Z";
}
