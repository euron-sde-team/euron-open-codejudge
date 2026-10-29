"use client";

import { ArrowLeftIcon, BarChart3Icon, CheckCircle2Icon, FileCode2Icon, ListChecksIcon, TargetIcon, TrendingUpIcon, UsersIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { AdminOnly } from "@/components/admin-only";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Segmented } from "@/components/segmented";
import { Stat } from "@/components/stat";
import { Surface, SurfaceHeader } from "@/components/surface";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { VerdictChip } from "@/components/verdict-chip";
import { LanguageName } from "@/components/language-name";
import { usePermissions } from "@/features/auth/api";
import { formatNumber, formatRatio, formatRelative } from "@/lib/format";
import { DIFFICULTY, formatScore, formatTime } from "@/lib/verdicts";

import { useLanguages } from "@/features/problems/api";

import { useMyProgress, useOverview, useProblemStats } from "../api";
import { DailyChart, RowBars, VerdictMixBar } from "./charts";

type Days = "7" | "30" | "90";
const DAY_OPTIONS = [
  { value: "7" as const, label: "7 days" },
  { value: "30" as const, label: "30 days" },
  { value: "90" as const, label: "90 days" },
];

const DIFF_COLOR: Record<string, string> = { easy: "var(--verdict-ac)", medium: "var(--verdict-tle)", hard: "var(--verdict-wa)" };

export function AnalyticsScreen() {
  const { user, staff } = usePermissions();
  const [days, setDays] = React.useState<Days>("30");
  const q = useOverview(Number(days));
  const languages = useLanguages();
  if (user && !staff) return <AdminOnly what="Analytics" />;
  const o = q.data;
  return (
    <>
      <PageHeader
        title="Analytics"
        description="How people are doing across every problem: activity, verdicts, what is hard and what is popular."
        actions={<Segmented<Days> ariaLabel="Period" value={days} onChange={setDays} options={DAY_OPTIONS} />}
      />
      {q.isError ? (
        <ErrorState error={q.error} title="Analytics could not be loaded" onRetry={() => void q.refetch()} />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Submissions" icon={ListChecksIcon} value={o ? formatNumber(o.submissions) : ""} loading={!o} />
            <Stat label="Accepted" icon={CheckCircle2Icon} value={o ? formatNumber(o.accepted) : ""} loading={!o} />
            <Stat label="Acceptance" icon={TargetIcon} value={o ? formatRatio(o.acceptance) : ""} loading={!o} detail="Accepted out of judged" />
            <Stat label="Active people" icon={UsersIcon} value={o ? formatNumber(o.active_users) : ""} loading={!o} detail="Submitted at least once" />
          </div>
          {!o ? (
            <Skeleton className="h-72 w-full" />
          ) : o.submissions === 0 ? (
            <div className="surface">
              <EmptyState
                icon={BarChart3Icon}
                title="No submissions in this period"
                description="Charts fill in as people submit. Try a longer period, or publish a problem and share it."
                action={
                  <Link href="/manage/problems" className={buttonVariants()}>
                    Problem editor
                  </Link>
                }
              />
            </div>
          ) : (
            <>
              <Surface className="p-5">
                <h2 className="mb-3 text-[14px] font-semibold">Submissions per day</h2>
                <DailyChart points={o.daily} days={o.days} />
              </Surface>
              <div className="grid gap-4 lg:grid-cols-2">
                <Surface className="p-5">
                  <h2 className="mb-3 text-[14px] font-semibold">Verdicts</h2>
                  <VerdictMixBar mix={o.verdicts} />
                </Surface>
                <Surface className="p-5">
                  <h2 className="mb-3 text-[14px] font-semibold">Acceptance by difficulty</h2>
                  <RowBars
                    rows={o.by_difficulty.map((d) => ({
                      label: DIFFICULTY[d.difficulty]?.label ?? d.difficulty,
                      value: d.acceptance ?? 0,
                      display: formatRatio(d.acceptance),
                      detail: `${formatNumber(d.submissions)} submissions`,
                      color: DIFF_COLOR[d.difficulty],
                    }))}
                  />
                </Surface>
                <Surface className="p-5">
                  <h2 className="mb-3 text-[14px] font-semibold">Languages</h2>
                  <RowBars
                    rows={o.languages.map((l) => ({
                      label: languages.data?.find((x) => x.id === l.language)?.name ?? l.language,
                      value: l.submissions,
                      display: formatNumber(l.submissions),
                      detail: `${formatRatio(l.submissions ? l.accepted / l.submissions : null)} accepted`,
                    }))}
                  />
                </Surface>
                <Surface>
                  <SurfaceHeader title="Most attempted problems" description="Open one for its statistics." />
                  <ul className="divide-y divide-hairline px-5 pb-3">
                    {o.top_problems.map((p) => (
                      <li key={p.problem_id}>
                        <Link href={`/analytics/problems/${p.slug}`} className="flex items-center gap-3 py-2 text-[13px] hover:text-primary">
                          <span className="min-w-0 flex-1 truncate font-medium">{p.title}</span>
                          <span className={`text-[12px] font-semibold ${DIFFICULTY[p.difficulty]?.className ?? ""}`}>{DIFFICULTY[p.difficulty]?.label}</span>
                          <span className="tabular w-20 text-right text-muted-foreground">{formatNumber(p.submissions)}</span>
                          <span className="tabular w-20 text-right">{formatRatio(p.acceptance)}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </Surface>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}

export function ProblemAnalyticsScreen({ slug }: { slug: string }) {
  const [days, setDays] = React.useState<Days>("30");
  const q = useProblemStats(slug, Number(days));
  const s = q.data;
  const attempts = s ? Object.entries(s.attempts_to_ac).sort((a, b) => Number(a[0].replace(/\D/g, "")) - Number(b[0].replace(/\D/g, ""))) : [];
  return (
    <div className="space-y-4">
      <Link href="/analytics" className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        Analytics
      </Link>
      <PageHeader
        title={s?.title ?? "Problem"}
        description="How people fare on this problem."
        actions={<Segmented<Days> ariaLabel="Period" value={days} onChange={setDays} options={DAY_OPTIONS} />}
      />
      {q.isError ? (
        <ErrorState error={q.error} title="Statistics could not be loaded" onRetry={() => void q.refetch()} />
      ) : !s ? (
        <Skeleton className="h-72 w-full" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Tried it" icon={UsersIcon} value={formatNumber(s.attempters)} detail={`${formatNumber(s.solvers)} solved it`} />
            <Stat label="Acceptance" icon={TargetIcon} value={formatRatio(s.acceptance)} detail={`${formatNumber(s.accepted)} of ${formatNumber(s.submissions)}`} />
            <Stat label="Tries to solve" icon={TrendingUpIcon} value={s.median_attempts_to_ac == null ? "n/a" : String(s.median_attempts_to_ac)} detail="Median, among solvers" />
            <Stat label="Accepted run time" icon={FileCode2Icon} value={s.median_ac_time_ms == null ? "n/a" : formatTime(s.median_ac_time_ms)} detail="Median CPU time" />
          </div>
          <Surface className="p-5">
            <h2 className="mb-3 text-[14px] font-semibold">Submissions per day</h2>
            <DailyChart points={s.daily} days={Number(days)} />
          </Surface>
          <div className="grid gap-4 lg:grid-cols-2">
            <Surface className="p-5">
              <h2 className="mb-3 text-[14px] font-semibold">Verdicts</h2>
              <VerdictMixBar mix={s.verdicts} />
            </Surface>
            <Surface className="p-5">
              <h2 className="mb-3 text-[14px] font-semibold">Tries before the first accept</h2>
              <RowBars rows={attempts.map(([k, v]) => ({ label: `${k} ${k === "1" ? "try" : "tries"}`, value: v, display: `${formatNumber(v)} people` }))} />
            </Surface>
          </div>
        </>
      )}
    </div>
  );
}

export function ProgressScreen() {
  const [days, setDays] = React.useState<Days>("30");
  const q = useMyProgress(Number(days));
  const p = q.data;
  const diffRows = p ? (["easy", "medium", "hard"] as const).map((d) => ({ label: DIFFICULTY[d]!.label, value: p.solved_by_difficulty[d] ?? 0, display: `${p.solved_by_difficulty[d] ?? 0} solved`, color: DIFF_COLOR[d] })) : [];
  return (
    <>
      <PageHeader
        title="My progress"
        description="Everything you have solved, and your activity over the period you choose."
        actions={<Segmented<Days> ariaLabel="Period" value={days} onChange={setDays} options={DAY_OPTIONS} />}
      />
      {q.isError ? (
        <ErrorState error={q.error} title="Your progress could not be loaded" onRetry={() => void q.refetch()} />
      ) : !p ? (
        <Skeleton className="h-72 w-full" />
      ) : p.submissions === 0 && p.solved === 0 ? (
        <div className="surface">
          <EmptyState
            icon={TrendingUpIcon}
            title="Nothing here yet"
            description="Solve your first problem and your progress shows up here: problems solved by difficulty, your activity and your recent results."
            action={
              <Link href="/problems" className={buttonVariants()}>
                Find a problem
              </Link>
            }
          />
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Solved" icon={CheckCircle2Icon} value={formatNumber(p.solved)} tone="good" />
            <Stat label="Tried, not solved yet" icon={TargetIcon} value={formatNumber(Math.max(0, p.attempted - p.solved))} />
            <Stat label="Submissions" icon={ListChecksIcon} value={formatNumber(p.submissions)} detail="All time" />
            <Stat label="Accepted" icon={TrendingUpIcon} value={formatRatio(p.submissions ? p.accepted_submissions / p.submissions : null)} detail="Of your submissions" />
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <Surface className="p-5">
              <h2 className="mb-3 text-[14px] font-semibold">Your activity</h2>
              <DailyChart points={p.activity} days={Number(days)} label="Your submissions per day" />
            </Surface>
            <Surface className="p-5">
              <h2 className="mb-3 text-[14px] font-semibold">Solved by difficulty</h2>
              <RowBars rows={diffRows} />
            </Surface>
          </div>
          <Surface>
            <SurfaceHeader title="Recent results" />
            {!p.recent.length ? (
              <p className="px-5 pb-4 text-[13px] text-muted-foreground">No submissions yet.</p>
            ) : (
              <ul className="divide-y divide-hairline px-5 pb-3">
                {p.recent.map((s) => (
                  <li key={s.id}>
                    <Link href={`/submissions/${s.id}`} className="flex flex-wrap items-center gap-3 py-2 text-[13px] hover:text-primary">
                      <span className="min-w-0 flex-1 truncate font-medium">{s.problem_title}</span>
                      <span className="text-muted-foreground"><LanguageName id={s.language} /></span>
                      <VerdictChip verdict={s.verdict} />
                      <span className="tabular w-20 text-right">{formatScore(s.score, s.max_score)}</span>
                      <span className="w-20 text-right text-muted-foreground">{formatRelative(s.created_at)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Surface>
        </div>
      )}
    </>
  );
}
