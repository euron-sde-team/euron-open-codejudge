"use client";

import { ArrowLeftIcon, CheckCircle2Icon, FileQuestionIcon, LogInIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Countdown } from "@/components/countdown";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Markdown } from "@/components/markdown";
import { Button, buttonVariants } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { VerdictChip } from "@/components/verdict-chip";
import { LanguageName } from "@/components/language-name";
import { usePermissions } from "@/features/auth/api";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { Contest, ContestStatus } from "@/lib/api/types";
import { loginUrl } from "@/lib/auth-redirect";
import { cn } from "@/lib/cn";
import { cellView, FORMAT_LABEL } from "@/lib/contest";
import { formatDateTime, formatRelative } from "@/lib/format";
import { formatScore } from "@/lib/verdicts";

import { useContest, useContestSubmissions, useMyContestStatus, useRegister } from "../api";
import { Clarifications } from "./clarifications";
import { ContestManage } from "./contest-manage";
import { ScoreboardView } from "./scoreboard";

type Tab = "problems" | "scoreboard" | "clarifications" | "submissions" | "manage";

const PHASE_CHIP: Record<string, { label: string; tone: "info" | "success" | "neutral" }> = {
  upcoming: { label: "Upcoming", tone: "info" },
  running: { label: "Running", tone: "success" },
  ended: { label: "Ended", tone: "neutral" },
};

export function ContestScreen({ slug }: { slug: string }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { signedIn, staff } = usePermissions();
  const contest = useContest(slug);
  const status = useMyContestStatus(slug, signedIn);
  const tab = (params.get("tab") as Tab | null) ?? "problems";
  const setTab = (t: string) => router.replace(t === "problems" ? pathname : `${pathname}?tab=${t}`, { scroll: false });

  if (contest.isPending) return <Skeleton className="h-64 w-full" />;
  if (contest.isError) {
    if (contest.error instanceof ApiError && contest.error.status === 404) {
      return (
        <EmptyState
          icon={FileQuestionIcon}
          title="This contest is not available"
          description="It may be private (join it with its code) or the link is mistyped."
          action={
            <Link href="/contests" className={buttonVariants()}>
              All contests
            </Link>
          }
        />
      );
    }
    return <ErrorState error={contest.error} title="The contest could not be loaded" onRetry={() => void contest.refetch()} />;
  }
  const c = contest.data;
  const registered = status.data?.registered ?? c.registered ?? false;

  return (
    <div className="space-y-5">
      <Link href="/contests" className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        Contests
      </Link>
      <Header contest={c} registered={registered} signedIn={signedIn} staff={staff} loginHref={loginUrl(pathname)} />
      <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
        <TabsList>
          <TabsTrigger value="problems">Problems</TabsTrigger>
          <TabsTrigger value="scoreboard">Scoreboard</TabsTrigger>
          {signedIn && <TabsTrigger value="clarifications">Clarifications</TabsTrigger>}
          {staff && <TabsTrigger value="submissions">Submissions</TabsTrigger>}
          {staff && <TabsTrigger value="manage">Manage</TabsTrigger>}
        </TabsList>
        <TabsContent value="problems">
          <ProblemsTab contest={c} status={status.data} registered={registered} staff={staff} />
        </TabsContent>
        <TabsContent value="scoreboard">
          <ScoreboardView contest={c} />
        </TabsContent>
        {signedIn && (
          <TabsContent value="clarifications">
            <Clarifications contest={c} registered={registered} />
          </TabsContent>
        )}
        {staff && (
          <TabsContent value="submissions">
            <ContestSubmissions contest={c} />
          </TabsContent>
        )}
        {staff && (
          <TabsContent value="manage">
            <ContestManage contest={c} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

function Header({ contest: c, registered, signedIn, staff, loginHref }: { contest: Contest; registered: boolean; signedIn: boolean; staff: boolean; loginHref: string }) {
  const register = useRegister(c.slug);
  const phase = PHASE_CHIP[c.phase] ?? PHASE_CHIP.ended!;
  const canRegister = signedIn && !registered && !staff && c.phase !== "ended" && c.registration === "open";
  return (
    <header className="surface flex flex-wrap items-start gap-4 p-5">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.02em]">{c.title}</h1>
          <Chip tone={phase.tone}>{phase.label}</Chip>
          <Chip tone="neutral">{c.format.toUpperCase()}</Chip>
        </div>
        <p className="mt-1 text-[12.5px] text-muted-foreground">
          {formatDateTime(c.starts_at)} to {formatDateTime(c.ends_at)}. {FORMAT_LABEL[c.format]}. {c.participants} registered.
        </p>
        {c.description_md && <Markdown source={c.description_md} className="mt-3 text-[13.5px]" />}
      </div>
      <div className="flex flex-col items-end gap-2">
        {c.phase === "running" && <Countdown to={c.ends_at} label="Ends in" className="text-[18px]" />}
        {c.phase === "upcoming" && <Countdown to={c.starts_at} label="Starts in" className="text-[18px]" />}
        {registered && (
          <span className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-verdict-ac">
            <CheckCircle2Icon className="size-4" aria-hidden />
            You are registered
          </span>
        )}
        {canRegister && (
          <Button
            disabled={register.isPending}
            onClick={() => register.mutate(undefined, { onSuccess: () => toast.success("Registered. Good luck."), onError: (e) => toast.error(errorMessage(e)) })}
          >
            Register
          </Button>
        )}
        {signedIn && !registered && !staff && c.registration === "invite" && c.phase !== "ended" && (
          <span className="max-w-56 text-right text-[12px] text-muted-foreground">Registration needs the join code: use Join with a code on the contests page.</span>
        )}
        {!signedIn && c.phase !== "ended" && (
          <Link href={loginHref} className={buttonVariants()}>
            <LogInIcon />
            Sign in to take part
          </Link>
        )}
      </div>
    </header>
  );
}

function ProblemsTab({ contest: c, status, registered, staff }: { contest: Contest; status: ContestStatus | undefined; registered: boolean; staff: boolean }) {
  if (!c.problems.length) {
    return (
      <div className="surface">
        <EmptyState
          icon={FileQuestionIcon}
          title={c.phase === "upcoming" ? "The problems appear when the contest starts" : "No problems in this contest"}
          description={c.phase === "upcoming" ? "Register now, then come back at the start time: the problem list unlocks for everyone at once." : "The organisers have not added problems yet."}
        />
      </div>
    );
  }
  const row = status?.row;
  return (
    <div className="space-y-3">
      {!registered && !staff && c.phase === "running" && (
        <p className="rounded-xl bg-info-soft px-4 py-3 text-[13px] text-info">Register to submit. You can read the problems either way.</p>
      )}
      <ul className="surface divide-y divide-hairline overflow-hidden">
        {c.problems.map((p) => {
          const cell = row?.cells.find((x) => x.label === p.label);
          const v = cellView(c.format, cell, p.points);
          return (
            <li key={p.label}>
              <Link href={`/contests/${c.slug}/problems/${p.label}`} className="flex items-center gap-4 px-4 py-3 hover:bg-muted/50 focus-visible:bg-muted/60 focus-visible:outline-none sm:px-5">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-[13px] font-semibold">{p.label}</span>
                <span className="min-w-0 flex-1 truncate text-[14px] font-medium">{p.title}</span>
                {c.format === "ioi" && <span className="tabular text-[12.5px] text-muted-foreground">{p.points} points</span>}
                <span
                  className={cn(
                    "min-w-20 text-right text-[12.5px] font-semibold",
                    v.tone === "solved" || v.tone === "first" ? "text-verdict-ac" : v.tone === "failed" ? "text-verdict-wa" : v.tone === "partial" ? "text-verdict-tle" : "text-muted-foreground",
                  )}
                >
                  {v.tone === "empty" ? "" : c.format === "ioi" ? formatScore(cell?.score ?? 0, p.points) : v.tone === "solved" || v.tone === "first" ? "Solved" : v.tone === "pending" ? "Pending" : `${cell?.attempts ?? 0} tries`}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      {row && (
        <p className="text-[12.5px] text-muted-foreground">
          You are ranked {row.rank}
          {c.format === "icpc" ? ` with ${row.solved} solved and ${row.penalty} penalty minutes.` : ` with ${Math.round(row.score * 100) / 100} points.`}
        </p>
      )}
    </div>
  );
}

function ContestSubmissions({ contest: c }: { contest: Contest }) {
  const [offset, setOffset] = React.useState(0);
  const subs = useContestSubmissions(c.id, offset, true);
  if (subs.isPending) return <p className="text-[13px] text-muted-foreground">Loading...</p>;
  if (subs.isError) return <ErrorState error={subs.error} title="Submissions could not be loaded" onRetry={() => void subs.refetch()} />;
  if (!subs.data.items.length) return <div className="surface"><EmptyState icon={FileQuestionIcon} title="No submissions yet" description="Every submission made during the contest is listed here as it arrives." /></div>;
  const labels = new Map(c.problems.map((p) => [p.problem_id, p.label]));
  return (
    <div className="space-y-3">
      <div className="surface overflow-x-auto">
        <table className="w-full min-w-[560px] text-[13px]">
          <thead>
            <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
              <th className="px-3 py-2.5 font-semibold">When</th>
              <th className="px-3 py-2.5 font-semibold">Who</th>
              <th className="px-3 py-2.5 font-semibold">Problem</th>
              <th className="px-3 py-2.5 font-semibold">Language</th>
              <th className="px-3 py-2.5 font-semibold">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {subs.data.items.map((s) => (
              <tr key={s.id} className="border-t border-hairline hover:bg-muted/40">
                <td className="px-3 py-2.5">
                  <Link href={`/submissions/${s.id}`} className="font-medium text-primary hover:underline">
                    {formatRelative(s.created_at)}
                  </Link>
                </td>
                <td className="px-3 py-2.5">{s.user_name ?? "Unknown"}</td>
                <td className="px-3 py-2.5">
                  {labels.get(s.problem_id) ?? ""} {s.problem_title}
                </td>
                <td className="px-3 py-2.5 text-muted-foreground"><LanguageName id={s.language} /></td>
                <td className="px-3 py-2.5">
                  <VerdictChip verdict={s.status === "done" ? s.verdict : "JUDGING"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {subs.data.total > 50 && (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - 50))}>
            Previous
          </Button>
          <Button size="sm" variant="secondary" disabled={offset + 50 >= subs.data.total} onClick={() => setOffset((o) => o + 50)}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
