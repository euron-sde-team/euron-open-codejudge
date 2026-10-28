"use client";

import { SnowflakeIcon, TrophyIcon } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { TableSkeleton } from "@/components/table-skeleton";
import { usePermissions } from "@/features/auth/api";
import type { Contest } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { cellView, freezeBanner } from "@/lib/contest";

import { useScoreboard } from "../api";

const TONE: Record<string, string> = {
  first: "bg-verdict-ac text-primary-foreground",
  solved: "bg-verdict-ac-soft text-verdict-ac",
  partial: "bg-verdict-tle-soft text-verdict-tle",
  failed: "bg-verdict-wa-soft text-verdict-wa",
  pending: "bg-info-soft text-info",
  empty: "",
};

export function ScoreboardView({ contest }: { contest: Contest }) {
  const { user, staff } = usePermissions();
  const board = useScoreboard(contest.slug, contest.phase === "running");

  if (board.isPending) return <div className="surface"><TableSkeleton rows={8} cols={6} /></div>;
  if (board.isError) return <ErrorState error={board.error} title="The scoreboard could not be loaded" onRetry={() => void board.refetch()} />;
  const b = board.data;
  const banner = freezeBanner(b, staff);
  const icpc = b.format === "icpc";

  return (
    <div className="space-y-3">
      {banner && (
        <div role="status" className={cn("flex items-start gap-2 rounded-xl px-4 py-3 text-[13px]", banner.tone === "warning" ? "bg-warning-soft text-warning" : "bg-info-soft text-info")}>
          <SnowflakeIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
          {banner.text}
        </div>
      )}
      {!b.rows.length ? (
        <div className="surface">
          <EmptyState
            icon={TrophyIcon}
            title="Nobody on the board yet"
            description={b.phase === "upcoming" ? "The board fills in once the contest starts and people submit." : "Registered people appear here once they submit."}
          />
        </div>
      ) : (
        <div className="surface overflow-x-auto">
          <table className="w-full min-w-max text-[13px]">
            <caption className="sr-only">
              Scoreboard, {icpc ? "ranked by problems solved, then penalty minutes" : "ranked by total points"}
            </caption>
            <thead>
              <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
                <th scope="col" className="w-12 px-3 py-2.5 text-right font-semibold">#</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Name</th>
                <th scope="col" className="px-3 py-2.5 text-right font-semibold">{icpc ? "Solved" : "Score"}</th>
                {icpc && <th scope="col" className="px-3 py-2.5 text-right font-semibold">Penalty</th>}
                {b.problems.map((p) => (
                  <th key={p.label} scope="col" className="w-16 px-1 py-2.5 text-center font-semibold" title={p.title}>
                    {p.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {b.rows.map((r) => {
                const me = user?.id === r.user_id;
                return (
                  <tr key={r.user_id} className={cn("border-t border-hairline", me && "bg-primary-soft/60")}>
                    <td className="tabular px-3 py-2 text-right font-semibold">{r.rank}</td>
                    <td className="max-w-[220px] truncate px-3 py-2 font-medium">
                      {r.name}
                      {me && <span className="ml-1.5 text-[11.5px] font-semibold text-primary">You</span>}
                    </td>
                    <td className="tabular px-3 py-2 text-right font-semibold">{icpc ? r.solved : Math.round(r.score * 100) / 100}</td>
                    {icpc && <td className="tabular px-3 py-2 text-right text-muted-foreground">{r.penalty}</td>}
                    {b.problems.map((p) => {
                      const cell = r.cells.find((c) => c.label === p.label);
                      const v = cellView(b.format, cell, p.points);
                      return (
                        <td key={p.label} className="px-1 py-1.5 text-center">
                          {v.tone === "empty" ? (
                            <span className="sr-only">{v.label}</span>
                          ) : (
                            <span className={cn("inline-flex min-w-12 flex-col items-center rounded-md px-1.5 py-1 leading-tight", TONE[v.tone])} title={v.label}>
                              <span className="tabular text-[12.5px] font-semibold">{v.text}</span>
                              {v.sub && <span className="tabular text-[10.5px] opacity-80">{v.sub}</span>}
                              <span className="sr-only">{v.label}</span>
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-[12px] text-muted-foreground">
        {icpc
          ? `Ranked by problems solved, then penalty: the minute of each solve plus ${contest.penalty_minutes} minutes per wrong try before it. A dark cell is the first solve of that problem.`
          : "Ranked by total points: each problem counts your best submission. Partial scores come from subtasks."}
        {contest.phase === "running" && " Refreshes every 10 seconds."}
      </p>
    </div>
  );
}
