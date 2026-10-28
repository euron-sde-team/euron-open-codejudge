"use client";

import { ArrowLeftIcon, DownloadIcon, EyeIcon, FileQuestionIcon, MoreHorizontalIcon, RefreshCwIcon, RocketIcon, Trash2Icon, UndoIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { AdminOnly } from "@/components/admin-only";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Hint } from "@/components/hint";
import { Button, buttonVariants } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePermissions } from "@/features/auth/api";
import { download } from "@/lib/api/client";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { ProblemAdmin } from "@/lib/api/types";

import { useDeleteProblem, useProblemAdmin, usePublish, useRejudgeProblem } from "../api";
import { DetailsTab } from "./details-tab";
import { SolutionsTab } from "./solutions-tab";
import { StatementTab } from "./statement-tab";
import { TestsTab } from "./tests-tab";
import { VersionsTab } from "./versions-tab";

type Tab = "details" | "statement" | "tests" | "solutions" | "versions";

export function ProblemEditorScreen({ id }: { id: string }) {
  const { user, staff } = usePermissions();
  const q = useProblemAdmin(id);
  const [tab, setTab] = React.useState<Tab>("statement");

  if (user && !staff) return <AdminOnly what="The problem editor" />;
  if (q.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-10 w-80" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (q.isError) {
    if (q.error instanceof ApiError && q.error.status === 404) {
      return (
        <EmptyState
          icon={FileQuestionIcon}
          title="This problem does not exist"
          description="It may have been deleted. The problem editor lists every problem."
          action={
            <Link href="/manage/problems" className={buttonVariants()}>
              All problems
            </Link>
          }
        />
      );
    }
    return <ErrorState error={q.error} title="The problem could not be loaded" onRetry={() => void q.refetch()} />;
  }

  const p = q.data;
  return (
    <div className="space-y-5">
      <Link href="/manage/problems" className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        Problem editor
      </Link>
      <Header problem={p} />
      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="statement">Statement</TabsTrigger>
          <TabsTrigger value="tests">Tests</TabsTrigger>
          <TabsTrigger value="solutions">Reference solutions</TabsTrigger>
          <TabsTrigger value="details">Details and limits</TabsTrigger>
          <TabsTrigger value="versions">Versions</TabsTrigger>
        </TabsList>
        <TabsContent value="statement">
          <StatementTab problem={p} />
        </TabsContent>
        <TabsContent value="tests">
          <TestsTab problem={p} />
        </TabsContent>
        <TabsContent value="solutions">
          <SolutionsTab problem={p} />
        </TabsContent>
        <TabsContent value="details">
          <DetailsTab problem={p} />
        </TabsContent>
        <TabsContent value="versions">
          <VersionsTab problem={p} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Header({ problem: p }: { problem: ProblemAdmin }) {
  const router = useRouter();
  const publish = usePublish(p.id);
  const rejudge = useRejudgeProblem(p.id);
  const remove = useDeleteProblem();
  const [confirm, setConfirm] = React.useState<"delete" | "rejudge" | null>(null);
  const published = p.status === "published";

  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.02em]">{p.title}</h1>
            {published ? <Chip tone="success">Published</Chip> : <Chip tone="warning">Draft</Chip>}
            {p.visibility === "private" && <Chip tone="neutral">Private</Chip>}
          </div>
          <p className="mt-1 font-mono text-[12px] text-faint">/problems/{p.slug}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Link href={`/problems/${p.slug}`} className={buttonVariants({ variant: "secondary", size: "sm" })}>
            <EyeIcon />
            View
          </Link>
          {published ? (
            <Button
              size="sm"
              variant="secondary"
              disabled={publish.isPending}
              onClick={() =>
                publish.mutate(false, {
                  onSuccess: () => toast.success("Unpublished. Students no longer see it."),
                  onError: (e) => toast.error(errorMessage(e)),
                })
              }
            >
              <UndoIcon />
              Unpublish
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={publish.isPending || !p.publishable}
              onClick={() =>
                publish.mutate(true, {
                  onSuccess: () => toast.success("Published. Students can solve it now."),
                  onError: (e) => toast.error(errorMessage(e)),
                })
              }
            >
              <RocketIcon />
              Publish
            </Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="subtle" size="icon-sm" aria-label="More actions" />}>
              <MoreHorizontalIcon />
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56">
              <DropdownMenuItem
                onClick={() =>
                  void download(`/api/v1/problems/${p.id}/export`, `${p.slug}.zip`).catch((e: unknown) => toast.error(errorMessage(e)))
                }
              >
                <DownloadIcon />
                Export package
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setConfirm("rejudge")}>
                <RefreshCwIcon />
                Rejudge all submissions
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={() => setConfirm("delete")}>
                <Trash2Icon />
                Delete problem
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {!published && (
        <div className={p.publishable ? "rounded-xl bg-savings-soft px-4 py-3 text-[13px] text-savings" : "rounded-xl bg-warning-soft px-4 py-3 text-[13px] text-warning"}>
          {p.publishable ? (
            "Ready to publish: the tests exist and every reference solution gets its expected verdict."
          ) : (
            <>
              <div className="flex items-center gap-1.5 font-semibold">
                Before publishing
                <Hint term="reference" />
              </div>
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {p.publish_blockers.map((b) => (
                  <li key={b}>{b.charAt(0).toUpperCase() + b.slice(1)}.</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
      <ConfirmDialog
        open={confirm === "rejudge"}
        onOpenChange={(o) => !o && setConfirm(null)}
        title="Rejudge every submission?"
        description="Every submission to this problem is judged again on the current tests. Verdicts and scoreboards update as results come in."
        confirmLabel="Rejudge all"
        pending={rejudge.isPending}
        onConfirm={() =>
          rejudge.mutate(undefined, {
            onSuccess: (r) => {
              toast.success(`${r.queued} submissions queued for judging again.`);
              setConfirm(null);
            },
            onError: (e) => toast.error(errorMessage(e)),
          })
        }
      />
      <ConfirmDialog
        open={confirm === "delete"}
        onOpenChange={(o) => !o && setConfirm(null)}
        title="Delete this problem?"
        description="The problem, its tests, reference solutions and every submission to it are deleted for good. Export the package first if you may need it again."
        confirmLabel="Delete for good"
        destructive
        pending={remove.isPending}
        onConfirm={() =>
          remove.mutate(p.id, {
            onSuccess: () => {
              toast.success("Problem deleted.");
              router.replace("/manage/problems");
            },
            onError: (e) => toast.error(errorMessage(e)),
          })
        }
      />
    </header>
  );
}
