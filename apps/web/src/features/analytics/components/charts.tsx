"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { CHART, ChartLegend, ChartTooltipCard } from "@/components/charts/chart-tooltip";
import type { DayPoint, VerdictMix } from "@/lib/api/types";
import { dailySeries, verdictColor, verdictSlices, type DaySeries } from "@/lib/analytics";
import { formatNumber, formatRatio } from "@/lib/format";
import { verdictSpec } from "@/lib/verdicts";

const axisProps = { stroke: CHART.axis, tick: { fill: CHART.axis, fontSize: 11 }, tickLine: false, axisLine: false } as const;
const dayFmt = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const ACCEPTED = "var(--verdict-ac)";
const REJECTED = "var(--chart-before)";

/** Submissions per day, accepted stacked under the rest. */
export function DailyChart({ points, days, label = "Submissions per day" }: { points: DayPoint[]; days: number; label?: string }) {
  const series = dailySeries(points, days);
  const total = series.reduce((s, d) => s + d.submissions, 0);
  const accepted = series.reduce((s, d) => s + d.accepted, 0);
  const step = Math.max(1, Math.ceil(series.length / 7));
  const ticks = series.filter((_, i) => i % step === 0).map((d) => d.day);
  return (
    <div className="flex flex-col gap-3">
      <ChartLegend
        items={[
          { label: "Accepted", color: ACCEPTED, value: formatNumber(accepted) },
          { label: "Not accepted", color: REJECTED, value: formatNumber(total - accepted) },
        ]}
      />
      <div className="h-[240px] w-full" role="img" aria-label={`${label}: ${total} submissions, ${accepted} accepted`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={series} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={CHART.grid} />
            <XAxis dataKey="day" ticks={ticks} tickFormatter={(d: string) => dayFmt.format(new Date(d))} {...axisProps} minTickGap={12} />
            <YAxis allowDecimals={false} width={36} {...axisProps} />
            <Tooltip
              cursor={{ fill: "var(--muted)", opacity: 0.5 }}
              content={({ active, payload }) => {
                const row = payload?.[0]?.payload as DaySeries | undefined;
                if (!active || !row) return null;
                return (
                  <ChartTooltipCard
                    title={dayFmt.format(new Date(row.day))}
                    rows={[
                      { label: "Accepted", value: formatNumber(row.accepted), color: ACCEPTED },
                      { label: "Not accepted", value: formatNumber(row.rejected), color: REJECTED },
                    ]}
                    footer={row.submissions ? `${formatRatio(row.accepted / row.submissions)} accepted` : "No submissions"}
                  />
                );
              }}
            />
            <Bar dataKey="accepted" stackId="s" fill={ACCEPTED} maxBarSize={22} />
            <Bar dataKey="rejected" stackId="s" fill={REJECTED} radius={[3, 3, 0, 0]} maxBarSize={22} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** The verdict mix as one stacked strip with a legend: shares at a glance, exact counts listed. */
export function VerdictMixBar({ mix }: { mix: VerdictMix }) {
  const slices = verdictSlices(mix);
  if (!slices.length) return <p className="text-[13px] text-muted-foreground">No judged submissions in this period.</p>;
  return (
    <div className="space-y-3">
      <div className="flex h-3 overflow-hidden rounded-full bg-muted" role="img" aria-label={slices.map((s) => `${verdictSpec(s.verdict).label} ${formatRatio(s.share)}`).join(", ")}>
        {slices.map((s) => (
          <div key={s.verdict} style={{ width: `${s.share * 100}%`, background: verdictColor(s.verdict) }} />
        ))}
      </div>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12.5px] sm:grid-cols-4">
        {slices.map((s) => (
          <li key={s.verdict} className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-[3px]" style={{ background: verdictColor(s.verdict) }} aria-hidden />
            <span className="text-muted-foreground">{verdictSpec(s.verdict).label}</span>
            <span className="tabular ml-auto font-semibold">{formatNumber(s.count)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A labelled horizontal bar per row: value against the largest. */
export function RowBars({ rows }: { rows: { label: string; value: number; display: string; detail?: string; color?: string }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (!rows.length) return <p className="text-[13px] text-muted-foreground">Nothing in this period.</p>;
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.label} className="text-[12.5px]">
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <span className="truncate font-medium">{r.label}</span>
            <span className="tabular shrink-0 text-muted-foreground">
              <span className="font-semibold text-foreground">{r.display}</span>
              {r.detail && <span>, {r.detail}</span>}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: r.color ?? CHART.after }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
