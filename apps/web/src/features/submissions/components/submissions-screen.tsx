"use client";

import { ListChecksIcon, RefreshCwIcon, SearchIcon, XIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { TableSkeleton } from "@/components/table-skeleton";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SimpleSelect } from "@/components/ui/select";
import { VerdictChip } from "@/components/verdict-chip";
import { usePermissions } from "@/features/auth/api";
import { useUsers } from "@/features/users/api";
import { errorMessage } from "@/lib/api/errors";
import type { Submission } from "@/lib/api/types";
import { formatNumber, formatRelative } from "@/lib/format";
import { formatMemory, formatScore, formatTime } from "@/lib/verdicts";

import { useRejudge, useSubmissions } from "../api";

const PAGE = 30;
const VERDICTS = ["AC", "WA", "TLE", "MLE", "RE", "OLE", "CE", "IE"];

export function SubmissionsScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { staff } = usePermissions();
  const problem = params.get("problem") ?? "";
  const verdict = params.get("verdict") ?? "";
  const userId = params.get("user") ?? "";
  const everyone = staff && params.get("scope") === "all";
  const page = Math.max(0, Number(params.get("page") ?? 0) || 0);
  const [problemText, setProblemText] = React.useState(problem);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const rejudge = useRejudge();
  const users = useUsers(staff && everyone);

  const setParams = React.useCallback(
    (changes: Record<string, string | null>) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(changes)) {
        if (!v) next.delete(k);
        else next.set(k, v);
      }
      if (!("page" in changes)) next.delete("page");
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  React.useEffect(() => {
    if (problemText === problem) return;
    const t = setTimeout(() => setParams({ problem: problemText.trim() || null }), 400);
    return () => clearTimeout(t);
  }, [problemText, problem, setParams]);

  const list = useSubmissions({
    problem,
    verdict,
    userId: everyone ? userId : "",
    mine: !everyone,
    limit: PAGE,
    offset: page * PAGE,
  });
  const items = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  const filtered = !!(problem || verdict || userId);

  function toggle(id: string) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function rejudgeSelected() {
    rejudge.mutate(
      { ids: [...selected] },
      {
        onSuccess: (r) => {
          toast.success(`${r.queued} submission${r.queued === 1 ? "" : "s"} queued for judging again.`);
          setSelected(new Set());
        },
        onError: (e) => toast.error(errorMessage(e)),
      },
    );
  }

  return (
    <>
      <PageHeader
        title="Submissions"
        description={everyone ? "Every submission on this server. Select some to judge them again." : "Everything you submitted, newest first."}
        actions={
          staff && (
            <div className="flex gap-2">
              <Button variant={everyone ? "secondary" : "default"} size="sm" onClick={() => setParams({ scope: null, user: null })}>
                Mine
              </Button>
              <Button variant={everyone ? "default" : "secondary"} size="sm" onClick={() => setParams({ scope: "all" })}>
                Everyone
              </Button>
            </div>
          )
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-60">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-faint" aria-hidden />
          <Input aria-label="Problem slug" placeholder="Problem slug" className="pl-9" value={problemText} onChange={(e) => setProblemText(e.target.value)} />
        </div>
        <SimpleSelect
          aria-label="Verdict"
          className="w-40"
          value={verdict}
          onValueChange={(v) => setParams({ verdict: v || null })}
          options={[{ value: "", label: "Any verdict" }, ...VERDICTS.map((v) => ({ value: v, label: v }))]}
        />
        {everyone && (
          <SimpleSelect
            aria-label="User"
            className="w-52"
            value={userId}
            onValueChange={(v) => setParams({ user: v || null })}
            options={[{ value: "", label: "Any user" }, ...(users.data ?? []).map((u) => ({ value: u.id, label: u.name }))]}
          />
        )}
        {filtered && (
          <Button
            variant="subtle"
            size="sm"
            onClick={() => {
              setProblemText("");
              setParams({ problem: null, verdict: null, user: null });
            }}
          >
            <XIcon />
            Clear filters
          </Button>
        )}
        {staff && selected.size > 0 && (
          <Button size="sm" className="ml-auto" disabled={rejudge.isPending} onClick={rejudgeSelected}>
            <RefreshCwIcon />
            Rejudge {selected.size}
          </Button>
        )}
      </div>

      <div className="surface overflow-x-auto">
        {list.isPending ? (
          <TableSkeleton rows={8} cols={6} />
        ) : list.isError ? (
          <ErrorState error={list.error} title="Submissions could not be loaded" onRetry={() => void list.refetch()} />
        ) : !items.length ? (
          filtered ? (
            <EmptyState icon={SearchIcon} title="Nothing matches these filters" description="Clear the filters to see every submission." />
          ) : (
            <EmptyState
              icon={ListChecksIcon}
              title={everyone ? "No submissions yet" : "You have not submitted anything yet"}
              description="A submission is your code judged on every test of a problem. Open a problem, write a solution and press Submit."
              action={
                <Link href="/problems" className={buttonVariants()}>
                  Find a problem
                </Link>
              }
            />
          )
        ) : (
          <table className="w-full min-w-[640px] text-[13px]">
            <thead>
              <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
                {staff && <th className="w-10 px-3 py-2.5" aria-label="Select" />}
                <th className="px-3 py-2.5 font-semibold">When</th>
                <th className="px-3 py-2.5 font-semibold">Problem</th>
                {everyone && <th className="px-3 py-2.5 font-semibold">Who</th>}
                <th className="px-3 py-2.5 font-semibold">Language</th>
                <th className="px-3 py-2.5 font-semibold">Verdict</th>
                <th className="px-3 py-2.5 text-right font-semibold">Score</th>
                <th className="px-3 py-2.5 text-right font-semibold">Time</th>
                <th className="hidden px-3 py-2.5 text-right font-semibold md:table-cell">Memory</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <Row key={s.id} s={s} staff={staff} everyone={everyone} selected={selected.has(s.id)} onToggle={() => toggle(s.id)} />
              ))}
            </tbody>
          </table>
        )}
      </div>
      {total > PAGE && (
        <nav aria-label="Pages" className="mt-4 flex items-center justify-between text-[13px] text-muted-foreground">
          <span>
            {page * PAGE + 1} to {Math.min(total, (page + 1) * PAGE)} of {formatNumber(total)}
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setParams({ page: String(page - 1) })}>
              Previous
            </Button>
            <Button variant="secondary" size="sm" disabled={(page + 1) * PAGE >= total} onClick={() => setParams({ page: String(page + 1) })}>
              Next
            </Button>
          </div>
        </nav>
      )}
    </>
  );
}

function Row({ s, staff, everyone, selected, onToggle }: { s: Submission; staff: boolean; everyone: boolean; selected: boolean; onToggle: () => void }) {
  const done = s.status === "done";
  return (
    <tr className="border-t border-hairline hover:bg-muted/40">
      {staff && (
        <td className="px-3 py-2.5">
          <input type="checkbox" className="size-4 accent-[var(--primary)]" checked={selected} onChange={onToggle} aria-label={`Select submission to ${s.problem_title ?? "problem"}`} />
        </td>
      )}
      <td className="px-3 py-2.5 whitespace-nowrap">
        <Link href={`/submissions/${s.id}`} className="font-medium text-primary hover:underline" title={s.created_at}>
          {formatRelative(s.created_at)}
        </Link>
      </td>
      <td className="max-w-[220px] truncate px-3 py-2.5">
        {s.problem_slug ? (
          <Link href={`/problems/${s.problem_slug}`} className="hover:underline">
            {s.problem_title}
          </Link>
        ) : (
          s.problem_title
        )}
        {s.late && <span className="ml-1.5 text-[11.5px] font-semibold text-warning">Late</span>}
      </td>
      {everyone && <td className="max-w-[160px] truncate px-3 py-2.5 text-muted-foreground">{s.user_name ?? "Candidate"}</td>}
      <td className="px-3 py-2.5 text-muted-foreground">{s.language}</td>
      <td className="px-3 py-2.5">
        <VerdictChip verdict={done ? s.verdict : s.status === "judging" ? "JUDGING" : "PENDING"} />
      </td>
      <td className="tabular px-3 py-2.5 text-right">{done && s.max_score ? formatScore(s.score, s.max_score) : ""}</td>
      <td className="tabular px-3 py-2.5 text-right text-muted-foreground">{done && s.verdict !== "CE" ? formatTime(s.time_ms) : ""}</td>
      <td className="tabular hidden px-3 py-2.5 text-right text-muted-foreground md:table-cell">{done && s.verdict !== "CE" ? formatMemory(s.memory_kb) : ""}</td>
    </tr>
  );
}
