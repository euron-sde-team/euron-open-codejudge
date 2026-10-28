/** Shaping analytics responses into chart series. */
import type { DayPoint, VerdictMix } from "./api/types";

export interface DaySeries {
  day: string;
  submissions: number;
  accepted: number;
  rejected: number;
}

/** One point per calendar day in the window, zero-filled, oldest first. */
export function dailySeries(points: DayPoint[], days: number, today: Date = new Date()): DaySeries[] {
  const byDay = new Map(points.map((p) => [String(p.day).slice(0, 10), p]));
  const out: DaySeries[] = [];
  const end = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  for (let i = days - 1; i >= 0; i -= 1) {
    const key = new Date(end - i * 86_400_000).toISOString().slice(0, 10);
    const p = byDay.get(key);
    const submissions = p?.submissions ?? 0;
    const accepted = p?.accepted ?? 0;
    out.push({ day: key, submissions, accepted, rejected: Math.max(0, submissions - accepted) });
  }
  return out;
}

export interface VerdictSlice {
  verdict: string;
  count: number;
  share: number;
}

const ORDER = ["AC", "WA", "TLE", "MLE", "RE", "OLE", "CE", "IE"] as const;

/** Verdicts with a count, in a fixed order, with their share of the total. */
export function verdictSlices(mix: VerdictMix): VerdictSlice[] {
  const total = ORDER.reduce((s, v) => s + (mix[v] ?? 0), 0);
  return ORDER.filter((v) => (mix[v] ?? 0) > 0).map((v) => ({ verdict: v, count: mix[v] ?? 0, share: total ? (mix[v] ?? 0) / total : 0 }));
}

/** CSS colour token for a verdict, matching the verdict chips. */
export function verdictColor(verdict: string): string {
  switch (verdict) {
    case "AC":
      return "var(--verdict-ac)";
    case "WA":
      return "var(--verdict-wa)";
    case "TLE":
      return "var(--verdict-tle)";
    case "MLE":
      return "var(--verdict-mle)";
    case "RE":
    case "OLE":
      return "var(--verdict-re)";
    case "CE":
      return "var(--verdict-ce)";
    default:
      return "var(--warning)";
  }
}
