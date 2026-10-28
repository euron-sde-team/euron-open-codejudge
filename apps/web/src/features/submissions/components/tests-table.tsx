"use client";

import { ChevronRightIcon } from "lucide-react";
import * as React from "react";

import { VerdictChip } from "@/components/verdict-chip";
import type { TestOutcome } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatMemory, formatTime, testLabel } from "@/lib/verdicts";

/**
 * Per-test results. Samples can be opened to see the program's output and the checker's
 * message; hidden tests show only their verdict, time and memory (by design: their data
 * is never sent to the browser).
 */
export function TestsTable({ tests, groups }: { tests: TestOutcome[]; groups?: Record<string, unknown>[] }) {
  const [open, setOpen] = React.useState<string | null>(null);
  if (!tests.length) return null;
  const points = new Map((groups ?? []).map((g) => [String(g.name), g]));
  return (
    <div className="overflow-hidden rounded-xl bg-muted/50">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
            <th className="px-3 py-2 font-semibold">Test</th>
            <th className="px-3 py-2 font-semibold">Verdict</th>
            <th className="px-3 py-2 text-right font-semibold">Time</th>
            <th className="hidden px-3 py-2 text-right font-semibold sm:table-cell">Memory</th>
          </tr>
        </thead>
        <tbody>
          {tests.map((t, i) => {
            const expandable = !!(t.output || t.message);
            const isOpen = open === t.name;
            const groupStart = i === 0 || tests[i - 1]?.group !== t.group;
            const g = points.get(t.group);
            return (
              <React.Fragment key={t.name}>
                {groupStart && points.size > 1 && (
                  <tr>
                    <td colSpan={4} className="px-3 pt-3 pb-1 text-[11.5px] font-semibold text-muted-foreground">
                      {t.group === "sample" ? "Samples" : `Group ${t.group}`}
                      {g && Number(g.points) > 0 && (
                        <span className="ml-2 font-normal text-faint">
                          {Number(g.earned ?? 0)} of {Number(g.points)} points
                        </span>
                      )}
                    </td>
                  </tr>
                )}
                <tr className="border-t border-hairline first:border-t-0">
                  <td className="px-3 py-2">
                    {expandable ? (
                      <button
                        type="button"
                        onClick={() => setOpen(isOpen ? null : t.name)}
                        aria-expanded={isOpen}
                        className="inline-flex items-center gap-1 rounded font-medium hover:text-primary focus-visible:outline-2 focus-visible:outline-ring"
                      >
                        <ChevronRightIcon className={cn("size-3.5 transition-transform", isOpen && "rotate-90")} aria-hidden />
                        {testLabel(t.name)}
                      </button>
                    ) : (
                      <span className="pl-[18px]">{testLabel(t.name)}</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <VerdictChip verdict={t.verdict} />
                  </td>
                  <td className="tabular px-3 py-2 text-right text-muted-foreground">{t.verdict === "SKIPPED" ? "" : formatTime(t.time_ms)}</td>
                  <td className="tabular hidden px-3 py-2 text-right text-muted-foreground sm:table-cell">
                    {t.verdict === "SKIPPED" ? "" : formatMemory(t.memory_kb)}
                  </td>
                </tr>
                {isOpen && (
                  <tr>
                    <td colSpan={4} className="px-3 pb-3">
                      {t.message && <p className="mb-2 text-[12.5px] text-muted-foreground">Checker: {t.message}</p>}
                      {t.output != null && (
                        <pre className="max-h-48 overflow-auto rounded-lg bg-code-bg p-3 font-mono text-[12px] text-code-fg">{t.output || "(no output)"}</pre>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
