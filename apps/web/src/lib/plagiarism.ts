/** Line highlighting for the side-by-side view of a flagged pair. */

/** The set of 1-based line numbers covered by [first, last] ranges (bounded by the file). */
export function highlightedLines(ranges: [number, number][] | number[][], lineCount: number): Set<number> {
  const out = new Set<number>();
  for (const r of ranges) {
    const start = Math.max(1, Math.min(r[0] ?? 0, r[1] ?? 0));
    const end = Math.min(lineCount, Math.max(r[0] ?? 0, r[1] ?? 0));
    for (let line = start; line <= end; line += 1) out.add(line);
  }
  return out;
}

/** 0.873 as "87%". */
export function similarityLabel(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** How alarming a similarity is, for colour. */
export function similarityTone(value: number): "danger" | "warning" | "neutral" {
  if (value >= 0.8) return "danger";
  if (value >= 0.6) return "warning";
  return "neutral";
}
