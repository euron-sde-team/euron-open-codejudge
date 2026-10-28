/**
 * Verdicts in plain words: one label, colour and explanation per verdict, so a result
 * reads the same on every screen.
 */

export type VerdictCode = "PENDING" | "JUDGING" | "AC" | "WA" | "TLE" | "MLE" | "RE" | "OLE" | "CE" | "SKIPPED" | "IE";

export interface VerdictSpec {
  code: string;
  short: string;
  label: string;
  hint: string;
  /** Tailwind classes for the chip: a soft fill with the verdict's colour as text. */
  className: string;
}

const SPECS: Record<VerdictCode, Omit<VerdictSpec, "code">> = {
  PENDING: { short: "Queued", label: "Queued", hint: "Waiting for a judge worker.", className: "bg-neutral-soft text-muted-foreground" },
  JUDGING: { short: "Judging", label: "Judging", hint: "A judge worker is compiling and running it now.", className: "bg-info-soft text-info" },
  AC: { short: "AC", label: "Accepted", hint: "Every test passed within the limits.", className: "bg-verdict-ac-soft text-verdict-ac" },
  WA: { short: "WA", label: "Wrong answer", hint: "The program ran but printed a different answer than expected.", className: "bg-verdict-wa-soft text-verdict-wa" },
  TLE: { short: "TLE", label: "Time limit exceeded", hint: "The program used more CPU time than the limit, or never finished.", className: "bg-verdict-tle-soft text-verdict-tle" },
  MLE: { short: "MLE", label: "Memory limit exceeded", hint: "The program needed more memory than the limit.", className: "bg-verdict-mle-soft text-verdict-mle" },
  RE: { short: "RE", label: "Runtime error", hint: "The program crashed or exited with a non-zero code.", className: "bg-verdict-re-soft text-verdict-re" },
  OLE: { short: "OLE", label: "Output limit exceeded", hint: "The program printed more than the output limit.", className: "bg-verdict-re-soft text-verdict-re" },
  CE: { short: "CE", label: "Compilation error", hint: "The code did not compile. The compiler output says why.", className: "bg-verdict-ce-soft text-verdict-ce" },
  SKIPPED: { short: "Skipped", label: "Skipped", hint: "Not run: an earlier test in the same group failed.", className: "bg-neutral-soft text-faint" },
  IE: { short: "IE", label: "Judge error", hint: "The judge failed, not your program. It is retried; staff can see the cause.", className: "bg-warning-soft text-warning" },
};

export function isVerdict(value: string): value is VerdictCode {
  return value in SPECS;
}

export function verdictSpec(value: string | null | undefined): VerdictSpec {
  const code = value ?? "PENDING";
  const spec = isVerdict(code) ? SPECS[code] : { short: code, label: code, hint: code, className: "bg-neutral-soft text-muted-foreground" };
  return { code, ...spec };
}

/** Verdicts that end a submission: the live view stops listening at one of these. */
export function isFinal(value: string | null | undefined): boolean {
  return !!value && value !== "PENDING" && value !== "JUDGING" && isVerdict(value);
}

/** 12 ms, 1.24 s. */
export function formatTime(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "n/a";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)} s`;
}

/** 812 KB, 12.4 MB. */
export function formatMemory(kb: number | null | undefined): string {
  if (kb == null || !Number.isFinite(kb)) return "n/a";
  if (kb < 1024) return `${Math.round(kb)} KB`;
  const mb = kb / 1024;
  return `${mb < 100 ? mb.toFixed(1) : Math.round(mb)} MB`;
}

/** 40 / 100, or 100 with no max. */
export function formatScore(score: number | null | undefined, max: number | null | undefined): string {
  if (score == null) return "n/a";
  const s = Number.isInteger(score) ? String(score) : score.toFixed(2).replace(/\.?0+$/, "");
  if (!max) return s;
  const m = Number.isInteger(max) ? String(max) : max.toFixed(2).replace(/\.?0+$/, "");
  return `${s} / ${m}`;
}

/** A test name for people: "sample/1" is "Sample 1", "secret/g1/03" is "Hidden g1/03". */
export function testLabel(name: string): string {
  const [kind, ...rest] = name.split("/");
  const tail = rest.join("/");
  if (kind === "sample") return `Sample ${tail}`;
  if (kind === "secret") return `Hidden ${tail}`;
  return name;
}

export const DIFFICULTY: Record<string, { label: string; className: string }> = {
  easy: { label: "Easy", className: "text-verdict-ac" },
  medium: { label: "Medium", className: "text-verdict-tle" },
  hard: { label: "Hard", className: "text-verdict-wa" },
};
