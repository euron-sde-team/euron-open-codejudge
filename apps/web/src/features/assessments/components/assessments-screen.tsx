"use client";

import { BriefcaseIcon, PlusIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { AdminOnly } from "@/components/admin-only";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { TableSkeleton } from "@/components/table-skeleton";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { FieldError } from "@/components/ui/label";
import { usePermissions } from "@/features/auth/api";
import { errorMessage } from "@/lib/api/errors";
import { formatRelative } from "@/lib/format";

import { useAssessments, useCreateAssessment } from "../api";
import { AssessmentFields, assessmentPayload, emptyAssessment, type AssessmentValues } from "./assessment-form";

export function AssessmentsScreen() {
  const { user, staff } = usePermissions();
  const list = useAssessments();
  const [open, setOpen] = React.useState(false);
  if (user && !staff) return <AdminOnly what="Interview assessments" />;
  return (
    <>
      <PageHeader
        title="Assessments"
        description="Timed coding interviews. Invite candidates by email; they take it from a one-time link without an account."
        actions={
          <Button onClick={() => setOpen(true)}>
            <PlusIcon />
            New assessment
          </Button>
        }
      />
      <div className="surface overflow-x-auto">
        {list.isPending ? (
          <TableSkeleton rows={4} cols={4} />
        ) : list.isError ? (
          <ErrorState error={list.error} title="Assessments could not be loaded" onRetry={() => void list.refetch()} />
        ) : !list.data.length ? (
          <EmptyState
            icon={BriefcaseIcon}
            title="No assessments yet"
            description="An assessment is a few problems with a time limit. Candidates get a link by email, take it in the browser, and you get a report with their code, scores and a timeline."
            action={
              <Button onClick={() => setOpen(true)}>
                <PlusIcon />
                New assessment
              </Button>
            }
          />
        ) : (
          <table className="w-full min-w-[600px] text-[13px]">
            <thead>
              <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
                <th className="px-4 py-2.5 font-semibold">Assessment</th>
                <th className="px-3 py-2.5 text-right font-semibold">Duration</th>
                <th className="px-3 py-2.5 text-right font-semibold">Invited</th>
                <th className="px-3 py-2.5 text-right font-semibold">Submitted</th>
                <th className="px-3 py-2.5 text-right font-semibold">Created</th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((a) => {
                const inv = a.invitations;
                const total = (inv.invited ?? 0) + (inv.started ?? 0) + (inv.submitted ?? 0) + (inv.expired ?? 0) + (inv.revoked ?? 0);
                return (
                  <tr key={a.id} className="border-t border-hairline hover:bg-muted/40">
                    <td className="px-4 py-2.5">
                      <Link href={`/assessments/${a.id}`} className="font-medium text-primary hover:underline">
                        {a.title}
                      </Link>
                      <div className="text-[12px] text-muted-foreground">
                        {a.problems.length} problem{a.problems.length === 1 ? "" : "s"}, {a.total_points} points
                      </div>
                    </td>
                    <td className="tabular px-3 py-2.5 text-right">{a.duration_minutes} min</td>
                    <td className="tabular px-3 py-2.5 text-right">{total}</td>
                    <td className="tabular px-3 py-2.5 text-right">{inv.submitted ?? 0}</td>
                    <td className="px-3 py-2.5 text-right text-muted-foreground">{formatRelative(a.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <CreateDialog open={open} onOpenChange={setOpen} />
    </>
  );
}

function CreateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const create = useCreateAssessment();
  const [values, setValues] = React.useState<AssessmentValues>(emptyAssessment);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (open) {
      setValues(emptyAssessment());
      setError(null);
    }
  }, [open]);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    const p = assessmentPayload(values);
    if (!p.ok) return setError(p.error);
    create.mutate(p.body, {
      onSuccess: (a) => {
        toast.success("Assessment created. Invite candidates next.");
        onOpenChange(false);
        router.push(`/assessments/${a.id}`);
      },
      onError: (err) => setError(errorMessage(err)),
    });
  }
  return (
    <Dialog open={open} onOpenChange={(o) => !create.isPending && onOpenChange(o)}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New assessment</DialogTitle>
          <DialogDescription>Use private problems so candidates cannot practise them beforehand.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogBody className="space-y-4">
            <AssessmentFields values={values} onChange={setValues} />
            {error && <FieldError>{error}</FieldError>}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating..." : "Create assessment"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
