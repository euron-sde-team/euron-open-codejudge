"use client";

import { ArrowLeftIcon, CalendarClockIcon, CheckCircle2Icon, DownloadIcon, FileQuestionIcon, Trash2Icon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { Countdown } from "@/components/countdown";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Markdown } from "@/components/markdown";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Button, buttonVariants } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { VerdictChip } from "@/components/verdict-chip";
import { usePermissions } from "@/features/auth/api";
import { download } from "@/lib/api/client";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { Assignment } from "@/lib/api/types";
import { gradebookCsvUrl, latePolicyText, STATUS_TEXT } from "@/lib/classes";
import { formatDateTime } from "@/lib/format";
import { fromLocalInput } from "@/lib/time";
import { DIFFICULTY, formatScore } from "@/lib/verdicts";

import { useAssignment, useClass, useDeleteAssignment, useExtension, useGradebook, useMembers, useUpdateAssignment } from "../api";
import { AssignmentFields, assignmentPayload, fromAssignment, type AssignmentValues } from "./assignment-form";

export function AssignmentScreen({ id }: { id: string }) {
  const { staff } = usePermissions();
  const a = useAssignment(id);
  const klass = useClass(a.data?.class_id ?? "");
  const teacher = staff || klass.data?.my_role === "teacher";

  if (a.isPending) return <Skeleton className="h-64 w-full" />;
  if (a.isError) {
    if (a.error instanceof ApiError && (a.error.status === 404 || a.error.status === 403)) {
      return (
        <EmptyState
          icon={FileQuestionIcon}
          title="This assignment is not available"
          description="It may not be open yet, or you are not in its class."
          action={
            <Link href="/classes" className={buttonVariants()}>
              My classes
            </Link>
          }
        />
      );
    }
    return <ErrorState error={a.error} title="The assignment could not be loaded" onRetry={() => void a.refetch()} />;
  }
  const as = a.data;
  return (
    <div className="space-y-5">
      <Link href={`/classes/${as.class_id}`} className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        {klass.data?.name ?? "Class"}
      </Link>
      <Header a={as} teacher={teacher} />
      {teacher ? (
        <Tabs defaultValue="problems">
          <TabsList>
            <TabsTrigger value="problems">Problems</TabsTrigger>
            <TabsTrigger value="gradebook">Gradebook</TabsTrigger>
            <TabsTrigger value="extensions">Extensions</TabsTrigger>
            <TabsTrigger value="edit">Edit</TabsTrigger>
          </TabsList>
          <TabsContent value="problems">
            <Problems a={as} teacher />
          </TabsContent>
          <TabsContent value="gradebook">
            <GradebookView a={as} />
          </TabsContent>
          <TabsContent value="extensions">
            <Extensions a={as} />
          </TabsContent>
          <TabsContent value="edit">
            <EditAssignment a={as} />
          </TabsContent>
        </Tabs>
      ) : (
        <Problems a={as} teacher={false} />
      )}
    </div>
  );
}

function Header({ a, teacher }: { a: Assignment; teacher: boolean }) {
  const extended = a.my_due_at !== a.due_at;
  return (
    <header className="surface space-y-3 p-5">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.02em]">{a.title}</h1>
            <Chip tone={a.status === "open" ? "success" : a.status === "late" ? "warning" : a.status === "upcoming" ? "info" : "neutral"}>{STATUS_TEXT[a.status] ?? a.status}</Chip>
          </div>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 text-[12.5px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <CalendarClockIcon className="size-3.5" aria-hidden />
              Opens {formatDateTime(a.opens_at)}, due {formatDateTime(a.my_due_at)}
            </span>
            {extended && !teacher && <span className="font-medium text-primary">Your due time was extended.</span>}
          </p>
          <p className="mt-1 text-[12.5px] text-muted-foreground">{latePolicyText(a.late_policy, a.penalty_percent)}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          {a.status === "open" && <Countdown to={a.my_due_at} label="Due in" className="text-[16px]" />}
          {!teacher && <span className="tabular text-[18px] font-semibold">{formatScore(a.my_total ?? 0, a.total_points)}</span>}
        </div>
      </div>
      {a.description_md && <Markdown source={a.description_md} className="text-[13.5px]" />}
    </header>
  );
}

function Problems({ a, teacher }: { a: Assignment; teacher: boolean }) {
  if (a.status === "upcoming" && !teacher) {
    return (
      <div className="surface">
        <EmptyState icon={CalendarClockIcon} title="Not open yet" description={`The problems appear at ${formatDateTime(a.opens_at)}. Come back then.`} />
      </div>
    );
  }
  return (
    <ul className="surface divide-y divide-hairline overflow-hidden">
      {a.problems.map((p) => {
        const full = p.my_score != null && p.my_score >= p.points;
        return (
          <li key={p.id}>
            <Link href={`/assignments/${a.id}/problems/${p.slug}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-muted/50 focus-visible:bg-muted/60 focus-visible:outline-none sm:px-5">
              <span className="flex size-5 items-center justify-center">{full && <CheckCircle2Icon className="size-4.5 text-verdict-ac" aria-label="Full marks" />}</span>
              <span className="min-w-0 flex-1 truncate text-[14px] font-medium">{p.title}</span>
              <span className={`text-[12.5px] font-semibold ${DIFFICULTY[p.difficulty]?.className ?? ""}`}>{DIFFICULTY[p.difficulty]?.label}</span>
              {!teacher && p.my_verdict && <VerdictChip verdict={p.my_verdict} />}
              <span className="tabular w-24 text-right text-[12.5px] font-semibold">{teacher ? `${p.points} points` : formatScore(p.my_score ?? 0, p.points)}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function GradebookView({ a }: { a: Assignment }) {
  const book = useGradebook(a.id, true);
  if (book.isPending) return <p className="text-[13px] text-muted-foreground">Loading...</p>;
  if (book.isError) return <ErrorState error={book.error} title="The gradebook could not be loaded" onRetry={() => void book.refetch()} />;
  const b = book.data;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[12.5px] text-muted-foreground">Best score per problem, after the late policy. Refreshes every 30 seconds.</p>
        <Button
          size="sm"
          variant="secondary"
          className="ml-auto"
          onClick={() => void download(gradebookCsvUrl(a.id), `${a.title}.csv`).catch((e: unknown) => toast.error(errorMessage(e)))}
        >
          <DownloadIcon />
          Download CSV
        </Button>
      </div>
      {!b.rows.length ? (
        <div className="surface">
          <EmptyState icon={FileQuestionIcon} title="No students yet" description="Students appear here once they join the class. Share the class code from the class page." />
        </div>
      ) : (
        <div className="surface overflow-x-auto">
          <table className="w-full min-w-max text-[13px]">
            <thead>
              <tr className="text-left text-[11.5px] tracking-wide text-faint uppercase">
                <th className="px-3 py-2.5 font-semibold">Student</th>
                {b.problems.map((p) => (
                  <th key={p.id} className="px-3 py-2.5 text-right font-semibold" title={p.title}>
                    {p.title.length > 18 ? `${p.title.slice(0, 17)}...` : p.title}
                  </th>
                ))}
                <th className="px-3 py-2.5 text-right font-semibold">Total</th>
              </tr>
            </thead>
            <tbody>
              {b.rows.map((r) => (
                <tr key={r.user_id} className="border-t border-hairline">
                  <td className="px-3 py-2">
                    <div className="font-medium">{r.name}</div>
                    <div className="text-[11.5px] text-muted-foreground">{r.email}</div>
                  </td>
                  {b.problems.map((p) => {
                    const cell = r.cells.find((c) => c.problem_id === p.id);
                    return (
                      <td key={p.id} className="tabular px-3 py-2 text-right">
                        {cell?.score == null ? (
                          <span className="text-faint">{cell?.attempts ? `${cell.attempts} tries` : ""}</span>
                        ) : (
                          <>
                            {Math.round(cell.score * 100) / 100}
                            {cell.late && <span className="ml-1 text-[11px] font-semibold text-warning">late</span>}
                          </>
                        )}
                      </td>
                    );
                  })}
                  <td className="tabular px-3 py-2 text-right font-semibold">{formatScore(r.total, b.total_points)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Extensions({ a }: { a: Assignment }) {
  const members = useMembers(a.class_id, true);
  const extend = useExtension(a.id);
  const [userId, setUserId] = React.useState("");
  const [due, setDue] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const students = (members.data ?? []).filter((m) => m.role === "student");
  return (
    <Surface>
      <SurfaceHeader title="Give one student more time" description="Their own due time moves; the late policy then applies from it. Setting it again replaces the extension." />
      <div className="flex flex-wrap items-end gap-2 px-5 pb-5">
        <Field label="Student" htmlFor="ext-user" className="w-64">
          <SimpleSelect id="ext-user" value={userId} onValueChange={setUserId} placeholder={students.length ? "Choose a student" : "No students yet"} options={students.map((m) => ({ value: m.user_id, label: m.name }))} />
        </Field>
        <Field label="New due time" htmlFor="ext-due">
          <Input id="ext-due" type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
        </Field>
        <Button
          disabled={extend.isPending}
          onClick={() => {
            const iso = fromLocalInput(due);
            if (!userId || !iso) return setError("Choose a student and a new due time.");
            setError(null);
            extend.mutate({ user_id: userId, due_at: iso }, { onSuccess: () => toast.success("Extension saved."), onError: (e) => setError(errorMessage(e)) });
          }}
        >
          Save extension
        </Button>
        {error && <FieldError className="w-full">{error}</FieldError>}
      </div>
    </Surface>
  );
}

function EditAssignment({ a }: { a: Assignment }) {
  const router = useRouter();
  const update = useUpdateAssignment(a.id);
  const del = useDeleteAssignment();
  const [values, setValues] = React.useState<AssignmentValues>(() => fromAssignment(a));
  const [error, setError] = React.useState<string | null>(null);
  const [deleting, setDeleting] = React.useState(false);
  return (
    <Surface className="max-w-3xl space-y-4 p-5">
      <AssignmentFields values={values} onChange={setValues} />
      {error && <FieldError>{error}</FieldError>}
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={update.isPending}
          onClick={() => {
            const p = assignmentPayload(values);
            if (!p.ok) return setError(p.error);
            setError(null);
            update.mutate(p.body, { onSuccess: () => toast.success("Assignment saved."), onError: (e) => setError(errorMessage(e)) });
          }}
        >
          {update.isPending ? "Saving..." : "Save assignment"}
        </Button>
        <Button variant="destructive-soft" className="ml-auto" onClick={() => setDeleting(true)}>
          <Trash2Icon />
          Delete assignment
        </Button>
      </div>
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title="Delete this assignment?"
        description="The assignment and its gradebook are deleted for good."
        confirmLabel="Delete assignment"
        destructive
        pending={del.isPending}
        onConfirm={() =>
          del.mutate(a.id, {
            onSuccess: () => {
              toast.success("Assignment deleted.");
              router.replace(`/classes/${a.class_id}`);
            },
            onError: (e) => toast.error(errorMessage(e)),
          })
        }
      />
    </Surface>
  );
}
