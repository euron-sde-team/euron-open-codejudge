"use client";

import { ArrowDownIcon, ArrowUpIcon, PlusIcon, SnowflakeIcon, Trash2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { CopyButton } from "@/components/copy-button";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { errorMessage } from "@/lib/api/errors";
import type { Contest } from "@/lib/api/types";
import { nextLabel } from "@/lib/contest";

import { useAddContestProblem, useDeleteContest, useRemoveContestProblem, useReorderContest, useUnfreeze, useUpdateContest } from "../api";
import { ContestFields, contestPayload, fromContest, type ContestFormValues } from "./contest-form";

export function ContestManage({ contest: c }: { contest: Contest }) {
  const router = useRouter();
  const update = useUpdateContest(c.id);
  const add = useAddContestProblem(c.id);
  const remove = useRemoveContestProblem(c.id);
  const reorder = useReorderContest(c.id);
  const unfreeze = useUnfreeze(c.id);
  const del = useDeleteContest();
  const [values, setValues] = React.useState<ContestFormValues>(() => fromContest(c));
  const [error, setError] = React.useState<string | null>(null);
  const [problem, setProblem] = React.useState("");
  const [points, setPoints] = React.useState("100");
  const [deleting, setDeleting] = React.useState(false);

  function save() {
    const p = contestPayload(values);
    if (!p.ok) return setError(p.error);
    setError(null);
    update.mutate(p.body, { onSuccess: () => toast.success("Contest saved."), onError: (e) => setError(errorMessage(e)) });
  }

  function move(index: number, delta: number) {
    const labels = c.problems.map((p) => p.label);
    const target = index + delta;
    if (target < 0 || target >= labels.length) return;
    [labels[index], labels[target]] = [labels[target]!, labels[index]!];
    reorder.mutate(labels, { onError: (e) => toast.error(errorMessage(e)) });
  }

  return (
    <div className="space-y-4">
      {c.join_code && (
        <Surface className="flex flex-wrap items-center gap-3 p-4">
          <span className="text-[13px] text-muted-foreground">Join code</span>
          <code className="rounded-lg bg-muted px-2.5 py-1 font-mono text-[14px] font-semibold tracking-wider">{c.join_code}</code>
          <CopyButton value={c.join_code} variant="ghost" label="Copy code" />
          <span className="text-[12px] text-muted-foreground">Contestants enter it under Contests, Join with a code.</span>
        </Surface>
      )}

      <Surface>
        <SurfaceHeader title="Problems" description="Labelled A, B, C in this order. Contestants see them only once the contest starts." />
        <div className="space-y-3 px-5 pb-5">
          {c.problems.length ? (
            <ul className="divide-y divide-hairline rounded-xl bg-muted/40">
              {c.problems.map((p, i) => (
                <li key={p.label} className="flex items-center gap-3 px-3 py-2 text-[13px]">
                  <span className="w-6 font-semibold">{p.label}</span>
                  <span className="min-w-0 flex-1 truncate">{p.title}</span>
                  <span className="tabular text-muted-foreground">{p.points} points</span>
                  <Button variant="subtle" size="icon-xs" aria-label={`Move ${p.label} up`} disabled={i === 0 || reorder.isPending} onClick={() => move(i, -1)}>
                    <ArrowUpIcon />
                  </Button>
                  <Button variant="subtle" size="icon-xs" aria-label={`Move ${p.label} down`} disabled={i === c.problems.length - 1 || reorder.isPending} onClick={() => move(i, 1)}>
                    <ArrowDownIcon />
                  </Button>
                  <Button
                    variant="subtle"
                    size="icon-xs"
                    aria-label={`Remove ${p.label}`}
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(p.label, { onError: (e) => toast.error(errorMessage(e)) })}
                  >
                    <Trash2Icon />
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-muted-foreground">No problems yet. Add problems by slug: private problems work too and stay hidden outside the contest.</p>
          )}
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Problem slug" htmlFor="cp-slug" className="w-56">
              <Input id="cp-slug" className="font-mono" value={problem} onChange={(e) => setProblem(e.target.value)} />
            </Field>
            {c.format === "ioi" && (
              <Field label="Points" htmlFor="cp-points" className="w-24">
                <Input id="cp-points" inputMode="decimal" value={points} onChange={(e) => setPoints(e.target.value)} />
              </Field>
            )}
            <Button
              variant="secondary"
              disabled={add.isPending || !problem.trim()}
              onClick={() =>
                add.mutate(
                  { problem: problem.trim(), label: nextLabel(c.problems.map((p) => p.label)), points: Number(points) || 100 },
                  {
                    onSuccess: () => {
                      setProblem("");
                      toast.success("Problem added.");
                    },
                    onError: (e) => toast.error(errorMessage(e)),
                  },
                )
              }
            >
              <PlusIcon />
              Add problem
            </Button>
          </div>
        </div>
      </Surface>

      <Surface>
        <SurfaceHeader title="Settings" />
        <div className="space-y-4 px-5 pb-5">
          <ContestFields values={values} onChange={setValues} withSlug={false} />
          {error && <FieldError>{error}</FieldError>}
          <div className="flex flex-wrap gap-2">
            <Button disabled={update.isPending} onClick={save}>
              {update.isPending ? "Saving..." : "Save settings"}
            </Button>
            {c.freeze_at && !c.unfrozen && (
              <Button
                variant="secondary"
                disabled={unfreeze.isPending}
                onClick={() => unfreeze.mutate(undefined, { onSuccess: () => toast.success("Unfrozen: everyone sees every result now."), onError: (e) => toast.error(errorMessage(e)) })}
              >
                <SnowflakeIcon />
                Unfreeze the scoreboard
              </Button>
            )}
            <Button variant="destructive-soft" className="ml-auto" onClick={() => setDeleting(true)}>
              <Trash2Icon />
              Delete contest
            </Button>
          </div>
        </div>
      </Surface>
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title="Delete this contest?"
        description="The contest, its problem list, registrations and clarifications are deleted for good."
        confirmLabel="Delete contest"
        destructive
        pending={del.isPending}
        onConfirm={() =>
          del.mutate(c.id, {
            onSuccess: () => {
              toast.success("Contest deleted.");
              router.replace("/contests");
            },
            onError: (e) => toast.error(errorMessage(e)),
          })
        }
      />
    </div>
  );
}
