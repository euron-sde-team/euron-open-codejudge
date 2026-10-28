"use client";

import { CheckCircle2Icon, CircleDotIcon, FileCode2Icon, SearchIcon, XIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Segmented } from "@/components/segmented";
import { TableSkeleton } from "@/components/table-skeleton";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SimpleSelect } from "@/components/ui/select";
import { usePermissions } from "@/features/auth/api";
import type { Difficulty, ProblemSummary } from "@/lib/api/types";
import { formatNumber, formatRatio } from "@/lib/format";
import { DIFFICULTY } from "@/lib/verdicts";

import { useProblems, useTags } from "../api";

const PAGE = 25;
type DifficultyFilter = Difficulty | "all";

export function ProblemsScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { signedIn, staff } = usePermissions();
  const q = params.get("q") ?? "";
  const tag = params.get("tag") ?? "";
  const difficulty = (params.get("difficulty") as DifficultyFilter | null) ?? "all";
  const page = Math.max(0, Number(params.get("page") ?? 0) || 0);
  const [search, setSearch] = React.useState(q);

  const setParams = React.useCallback(
    (changes: Record<string, string | null>) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(changes)) {
        if (v === null || v === "" || v === "all") next.delete(k);
        else next.set(k, v);
      }
      if (!("page" in changes)) next.delete("page");
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  // Search as you type, a moment after typing stops.
  React.useEffect(() => {
    if (search === q) return;
    const t = setTimeout(() => setParams({ q: search.trim() || null }), 300);
    return () => clearTimeout(t);
  }, [search, q, setParams]);

  const problems = useProblems({ q, tag, difficulty: difficulty === "all" ? "" : difficulty, limit: PAGE, offset: page * PAGE });
  const tags = useTags();
  const total = problems.data?.total ?? 0;
  const filtered = !!(q || tag || difficulty !== "all");

  return (
    <>
      <PageHeader
        title="Problems"
        description={
          signedIn
            ? "Pick a problem, solve it in the editor, and get a verdict on hidden tests in seconds."
            : "Browse freely. Sign in to run your code and submit it for a verdict."
        }
        actions={
          staff && (
            <Link href="/manage/problems" className={buttonVariants({ variant: "secondary" })}>
              Manage problems
            </Link>
          )
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-faint" aria-hidden />
          <Input
            type="search"
            aria-label="Search problems"
            placeholder="Search by title"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <SimpleSelect
          aria-label="Tag"
          className="w-44"
          placeholder="Any tag"
          value={tag}
          onValueChange={(v) => setParams({ tag: v || null })}
          options={[{ value: "", label: "Any tag" }, ...(tags.data ?? []).map((t) => ({ value: t.tag, label: `${t.tag} (${t.problems})` }))]}
        />
        <Segmented<DifficultyFilter>
          ariaLabel="Difficulty"
          value={difficulty}
          onChange={(v) => setParams({ difficulty: v })}
          options={[
            { value: "all", label: "All" },
            { value: "easy", label: "Easy" },
            { value: "medium", label: "Medium" },
            { value: "hard", label: "Hard" },
          ]}
        />
        {filtered && (
          <Button
            variant="subtle"
            size="sm"
            onClick={() => {
              setSearch("");
              setParams({ q: null, tag: null, difficulty: null });
            }}
          >
            <XIcon />
            Clear filters
          </Button>
        )}
      </div>

      <div className="surface overflow-hidden">
        {problems.isPending ? (
          <TableSkeleton rows={8} cols={4} />
        ) : problems.isError ? (
          <ErrorState error={problems.error} title="The problems could not be loaded" onRetry={() => void problems.refetch()} />
        ) : !problems.data.items.length ? (
          filtered ? (
            <EmptyState
              icon={SearchIcon}
              title="No problem matches these filters"
              description="Try another word, tag or difficulty, or clear the filters to see every problem."
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSearch("");
                    setParams({ q: null, tag: null, difficulty: null });
                  }}
                >
                  Clear filters
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={FileCode2Icon}
              title="No problems yet"
              description={
                staff
                  ? "Problems are written by staff: a statement, tests and a reference solution. Create one, or import a Kattis package."
                  : "Problems appear here once staff publish them. Check back soon."
              }
              action={
                staff && (
                  <Link href="/manage/problems" className={buttonVariants()}>
                    Create a problem
                  </Link>
                )
              }
            />
          )
        ) : (
          <ul className="divide-y divide-hairline">
            {problems.data.items.map((p) => (
              <ProblemRow key={p.id} problem={p} />
            ))}
          </ul>
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

function ProblemRow({ problem: p }: { problem: ProblemSummary }) {
  const d = DIFFICULTY[p.difficulty];
  return (
    <li>
      <Link
        href={`/problems/${p.slug}`}
        className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/50 focus-visible:bg-muted/60 focus-visible:outline-none sm:px-5"
      >
        <span className="flex size-5 shrink-0 items-center justify-center" aria-label={p.mine === "solved" ? "Solved" : p.mine === "attempted" ? "Attempted" : undefined}>
          {p.mine === "solved" ? (
            <CheckCircle2Icon className="size-4.5 text-verdict-ac" />
          ) : p.mine === "attempted" ? (
            <CircleDotIcon className="size-4 text-verdict-tle" />
          ) : null}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14px] font-medium">{p.title}</span>
          {p.tags.length > 0 && <span className="mt-0.5 block truncate text-[12px] text-muted-foreground">{p.tags.join(", ")}</span>}
        </span>
        {p.status === "draft" && <span className="hidden text-[11.5px] font-semibold text-warning sm:inline">Draft</span>}
        {d && <span className={`w-16 text-right text-[12.5px] font-semibold ${d.className}`}>{d.label}</span>}
        <span className="tabular hidden w-24 text-right text-[12.5px] text-muted-foreground md:block" title="Accepted out of judged submissions">
          {p.acceptance == null ? "No tries" : `${formatRatio(p.acceptance)} accepted`}
        </span>
        <span className="tabular hidden w-20 text-right text-[12.5px] text-muted-foreground lg:block">
          {formatNumber(p.solvers_count)} solved
        </span>
      </Link>
    </li>
  );
}
