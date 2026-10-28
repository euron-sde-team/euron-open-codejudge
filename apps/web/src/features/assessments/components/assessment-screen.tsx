"use client";

import { ArrowLeftIcon, FileQuestionIcon, MailIcon, RotateCwIcon, SendIcon, Trash2Icon, UserXIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Button, buttonVariants } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Textarea } from "@/components/ui/input";
import { FieldError } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { Assessment, Invitation } from "@/lib/api/types";
import { formatDateTime, formatRelative } from "@/lib/format";
import { parseCandidates } from "@/lib/invites";
import { formatScore } from "@/lib/verdicts";

import { useAssessment, useDeleteAssessment, useInvitations, useInvite, useResend, useRevoke, useUpdateAssessment } from "../api";
import { AssessmentFields, assessmentPayload, fromAssessment, type AssessmentValues } from "./assessment-form";

export const INVITATION_STATUS: Record<string, { label: string; tone: "neutral" | "info" | "success" | "warning" | "danger" }> = {
  invited: { label: "Invited", tone: "neutral" },
  started: { label: "In progress", tone: "info" },
  submitted: { label: "Submitted", tone: "success" },
  expired: { label: "Time ran out", tone: "warning" },
  revoked: { label: "Revoked", tone: "danger" },
};

export function AssessmentScreen({ id }: { id: string }) {
  const a = useAssessment(id);
  if (a.isPending) return <Skeleton className="h-64 w-full" />;
  if (a.isError) {
    if (a.error instanceof ApiError && a.error.status === 404) {
      return (
        <EmptyState
          icon={FileQuestionIcon}
          title="This assessment does not exist"
          description="It may have been deleted."
          action={
            <Link href="/assessments" className={buttonVariants()}>
              All assessments
            </Link>
          }
        />
      );
    }
    return <ErrorState error={a.error} title="The assessment could not be loaded" onRetry={() => void a.refetch()} />;
  }
  const as = a.data;
  return (
    <div className="space-y-5">
      <Link href="/assessments" className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        Assessments
      </Link>
      <header>
        <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.02em]">{as.title}</h1>
        <p className="mt-1 text-[12.5px] text-muted-foreground">
          {as.duration_minutes} minutes, {as.problems.length} problem{as.problems.length === 1 ? "" : "s"} ({as.problems.map((p) => p.title).join(", ")}), {as.total_points} points
          {as.closes_at && `. Closes ${formatDateTime(as.closes_at)}`}.
        </p>
      </header>
      <Tabs defaultValue="candidates">
        <TabsList>
          <TabsTrigger value="candidates">Candidates</TabsTrigger>
          <TabsTrigger value="edit">Edit</TabsTrigger>
        </TabsList>
        <TabsContent value="candidates">
          <Candidates assessment={as} />
        </TabsContent>
        <TabsContent value="edit">
          <Edit assessment={as} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Candidates({ assessment: a }: { assessment: Assessment }) {
  const list = useInvitations(a.id);
  const invite = useInvite(a.id);
  const resend = useResend(a.id);
  const revoke = useRevoke(a.id);
  const [text, setText] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [revoking, setRevoking] = React.useState<Invitation | null>(null);

  function send() {
    const { candidates, invalid } = parseCandidates(text);
    if (invalid.length) return setError(`These lines are not an email address: ${invalid.slice(0, 3).join("; ")}${invalid.length > 3 ? "..." : ""}`);
    if (!candidates.length) return setError("Add at least one email address.");
    setError(null);
    invite.mutate(candidates, {
      onSuccess: (r) => {
        setText("");
        const failed = r.failed ?? [];
        if (failed.length) toast.warning(`${r.invitations.length - failed.length} sent. Mail failed for ${failed.join(", ")}: resend them later.`);
        else toast.success(`${r.invitations.length} invitation${r.invitations.length === 1 ? "" : "s"} sent.`);
      },
      onError: (e) => setError(errorMessage(e)),
    });
  }

  return (
    <div className="space-y-4">
      <Surface>
        <SurfaceHeader title="Invite candidates" description='One per line: an email, "Name, email" or "Name <email>". Each gets a personal one-time link.' />
        <div className="space-y-3 px-5 pb-5">
          <Textarea aria-label="Candidates, one per line" rows={4} className="font-mono text-[12.5px]" value={text} onChange={(e) => setText(e.target.value)} placeholder={"Ada Lovelace <ada@example.com>\nalan@example.com"} />
          {error && <FieldError>{error}</FieldError>}
          <Button disabled={invite.isPending || !text.trim()} onClick={send}>
            <SendIcon />
            {invite.isPending ? "Sending..." : "Send invitations"}
          </Button>
        </div>
      </Surface>
      <Surface>
        <SurfaceHeader title="Candidates" description="Refreshes every 20 seconds. Open a report once someone has started." />
        {list.isPending ? (
          <p className="px-5 pb-4 text-[13px] text-muted-foreground">Loading...</p>
        ) : list.isError ? (
          <ErrorState compact error={list.error} title="Candidates could not be loaded" onRetry={() => void list.refetch()} />
        ) : !list.data.length ? (
          <EmptyState compact icon={MailIcon} title="Nobody invited yet" description="Add candidates above. Their status, score and report appear here." />
        ) : (
          <div className="overflow-x-auto px-2 pb-2">
            <table className="w-full min-w-[640px] text-[13px]">
              <thead>
                <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
                  <th className="px-3 py-2 font-semibold">Candidate</th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                  <th className="px-3 py-2 text-right font-semibold">Score</th>
                  <th className="px-3 py-2 text-right font-semibold">Signals</th>
                  <th className="px-3 py-2 font-semibold">Updated</th>
                  <th className="px-3 py-2" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {list.data.map((inv) => {
                  const st = INVITATION_STATUS[inv.status] ?? { label: inv.status, tone: "neutral" as const };
                  const started = inv.status !== "invited" && inv.status !== "revoked";
                  return (
                    <tr key={inv.id} className="border-t border-hairline">
                      <td className="px-3 py-2">
                        <div className="font-medium">{inv.name || inv.email}</div>
                        {inv.name && <div className="text-[11.5px] text-muted-foreground">{inv.email}</div>}
                      </td>
                      <td className="px-3 py-2">
                        <Chip tone={st.tone}>{st.label}</Chip>
                      </td>
                      <td className="tabular px-3 py-2 text-right">{inv.score == null ? "" : formatScore(inv.score, a.total_points)}</td>
                      <td className="tabular px-3 py-2 text-right" title="Pastes and tab switches recorded">
                        {started ? inv.signals : ""}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">{formatRelative(inv.submitted_at ?? inv.started_at ?? inv.sent_at ?? inv.created_at)}</td>
                      <td className="px-3 py-2">
                        <div className="flex justify-end gap-1">
                          {started && (
                            <Link href={`/assessments/${a.id}/invitations/${inv.id}`} className={buttonVariants({ size: "xs", variant: "secondary" })}>
                              Report
                            </Link>
                          )}
                          {(inv.status === "invited" || inv.status === "started") && (
                            <Button
                              size="icon-xs"
                              variant="subtle"
                              aria-label={`Resend to ${inv.email}`}
                              title="Resend the invitation (a new link; the old one stops working)"
                              disabled={resend.isPending}
                              onClick={() => resend.mutate(inv.id, { onSuccess: () => toast.success(`Resent to ${inv.email}.`), onError: (e) => toast.error(errorMessage(e)) })}
                            >
                              <RotateCwIcon />
                            </Button>
                          )}
                          {(inv.status === "invited" || inv.status === "started") && (
                            <Button size="icon-xs" variant="subtle" aria-label={`Revoke ${inv.email}`} title="Revoke the link" onClick={() => setRevoking(inv)}>
                              <UserXIcon />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Surface>
      <ConfirmDialog
        open={!!revoking}
        onOpenChange={(o) => !o && setRevoking(null)}
        title={`Revoke the link for ${revoking?.email ?? "this candidate"}?`}
        description="The link stops working at once, also in the middle of the assessment. What they submitted so far is kept."
        confirmLabel="Revoke"
        destructive
        pending={revoke.isPending}
        onConfirm={() => revoking && revoke.mutate(revoking.id, { onSuccess: () => setRevoking(null), onError: (e) => toast.error(errorMessage(e)) })}
      />
    </div>
  );
}

function Edit({ assessment: a }: { assessment: Assessment }) {
  const router = useRouter();
  const update = useUpdateAssessment(a.id);
  const del = useDeleteAssessment();
  const [values, setValues] = React.useState<AssessmentValues>(() => fromAssessment(a));
  const [error, setError] = React.useState<string | null>(null);
  const [deleting, setDeleting] = React.useState(false);
  return (
    <Surface className="max-w-3xl space-y-4 p-5">
      <AssessmentFields values={values} onChange={setValues} />
      {error && <FieldError>{error}</FieldError>}
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={update.isPending}
          onClick={() => {
            const p = assessmentPayload(values);
            if (!p.ok) return setError(p.error);
            setError(null);
            update.mutate(p.body, { onSuccess: () => toast.success("Assessment saved."), onError: (e) => setError(errorMessage(e)) });
          }}
        >
          {update.isPending ? "Saving..." : "Save assessment"}
        </Button>
        <Button variant="destructive-soft" className="ml-auto" onClick={() => setDeleting(true)}>
          <Trash2Icon />
          Delete assessment
        </Button>
      </div>
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title="Delete this assessment?"
        description="The assessment, its invitations and reports are deleted for good. Open links stop working."
        confirmLabel="Delete assessment"
        destructive
        pending={del.isPending}
        onConfirm={() =>
          del.mutate(a.id, {
            onSuccess: () => {
              toast.success("Assessment deleted.");
              router.replace("/assessments");
            },
            onError: (e) => toast.error(errorMessage(e)),
          })
        }
      />
    </Surface>
  );
}
