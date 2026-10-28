"use client";

import { CalendarClockIcon, GraduationCapIcon, KeyRoundIcon, PlusIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { TableSkeleton } from "@/components/table-skeleton";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { usePermissions } from "@/features/auth/api";
import { errorMessage } from "@/lib/api/errors";
import { formatDateTime, formatRelative } from "@/lib/format";
import { formatScore } from "@/lib/verdicts";

import { useClasses, useCreateClass, useJoinClass, useMyAssignments } from "../api";

export function ClassesScreen() {
  const { staff } = usePermissions();
  const classes = useClasses();
  const mine = useMyAssignments();
  const [joinOpen, setJoinOpen] = React.useState(false);
  const [createOpen, setCreateOpen] = React.useState(false);
  const due = (mine.data ?? []).filter((a) => a.status === "open" || a.status === "late").sort((a, b) => a.my_due_at.localeCompare(b.my_due_at));

  return (
    <>
      <PageHeader
        title="Classes"
        description="Your classes and their assignments. Join a class with the code your teacher shares."
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setJoinOpen(true)}>
              <KeyRoundIcon />
              Join a class
            </Button>
            {staff && (
              <Button onClick={() => setCreateOpen(true)}>
                <PlusIcon />
                New class
              </Button>
            )}
          </div>
        }
      />
      {due.length > 0 && (
        <section className="mb-6" aria-label="Due soon">
          <h2 className="mb-2 text-[13px] font-semibold text-muted-foreground">Due soon</h2>
          <ul className="surface divide-y divide-hairline overflow-hidden">
            {due.map((a) => (
              <li key={a.id}>
                <Link href={`/assignments/${a.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-muted/50 sm:px-5">
                  <span className="min-w-0 flex-1 truncate text-[14px] font-medium">{a.title}</span>
                  <span className="inline-flex items-center gap-1 text-[12.5px] text-muted-foreground">
                    <CalendarClockIcon className="size-3.5" aria-hidden />
                    Due {formatRelative(a.my_due_at)}
                  </span>
                  {a.status === "late" && <Chip tone="warning">Past due</Chip>}
                  <span className="tabular w-24 text-right text-[12.5px] font-semibold">{formatScore(a.my_total ?? 0, a.total_points)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      {classes.isPending ? (
        <div className="surface">
          <TableSkeleton rows={4} cols={3} />
        </div>
      ) : classes.isError ? (
        <ErrorState error={classes.error} title="Classes could not be loaded" onRetry={() => void classes.refetch()} />
      ) : !classes.data.length ? (
        <div className="surface">
          <EmptyState
            icon={GraduationCapIcon}
            title="You are not in a class yet"
            description={
              staff
                ? "A class groups students, with assignments that have due dates and a gradebook. Create one and share its join code."
                : "Ask your teacher for the class code, then join: your assignments and due dates appear here."
            }
            action={
              staff ? (
                <Button onClick={() => setCreateOpen(true)}>
                  <PlusIcon />
                  New class
                </Button>
              ) : (
                <Button onClick={() => setJoinOpen(true)}>Join a class</Button>
              )
            }
          />
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {classes.data.map((c) => (
            <li key={c.id}>
              <Link href={`/classes/${c.id}`} className="surface flex h-full flex-col gap-1 p-4 transition-shadow hover:shadow-[var(--elev-3)] focus-visible:outline-2 focus-visible:outline-ring">
                <span className="flex items-center gap-2">
                  <span className="truncate text-[15px] font-semibold">{c.name}</span>
                  {c.my_role === "teacher" && <Chip tone="primary">Teacher</Chip>}
                  {c.archived && <Chip tone="neutral">Archived</Chip>}
                </span>
                {c.description && <span className="line-clamp-2 text-[12.5px] text-muted-foreground">{c.description}</span>}
                <span className="mt-auto pt-2 text-[12px] text-muted-foreground">
                  {c.students} students, {c.assignments} assignment{c.assignments === 1 ? "" : "s"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {mine.data && mine.data.some((a) => a.status === "upcoming") && (
        <p className="mt-4 text-[12.5px] text-muted-foreground">
          Next to open: {mine.data.filter((a) => a.status === "upcoming").map((a) => `${a.title} (${formatDateTime(a.opens_at)})`).join(", ")}.
        </p>
      )}
      <JoinDialog open={joinOpen} onOpenChange={setJoinOpen} />
      <CreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </>
  );
}

function JoinDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const join = useJoinClass();
  const [code, setCode] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (open) {
      setCode("");
      setError(null);
    }
  }, [open]);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (code.trim().length < 4) return setError("Enter the code your teacher gave you.");
    join.mutate(code.trim(), {
      onSuccess: (c) => {
        toast.success(`You joined ${c.name}.`);
        onOpenChange(false);
        router.push(`/classes/${c.id}`);
      },
      onError: (err) => setError(errorMessage(err)),
    });
  }
  return (
    <Dialog open={open} onOpenChange={(o) => !join.isPending && onOpenChange(o)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Join a class</DialogTitle>
          <DialogDescription>Your teacher shares a short code for the class.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogBody>
            <Field label="Class code" htmlFor="class-code">
              <Input id="class-code" autoFocus autoComplete="off" className="font-mono uppercase" value={code} onChange={(e) => setCode(e.target.value)} />
            </Field>
            {error && <FieldError className="mt-3">{error}</FieldError>}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={join.isPending}>
              {join.isPending ? "Joining..." : "Join"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CreateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const create = useCreateClass();
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (open) {
      setName("");
      setDescription("");
      setError(null);
    }
  }, [open]);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("Name the class, for example: Algorithms, Spring term.");
    create.mutate(
      { name: name.trim(), description: description.trim() },
      {
        onSuccess: (c) => {
          toast.success("Class created. Share its code with your students.");
          onOpenChange(false);
          router.push(`/classes/${c.id}?tab=roster`);
        },
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }
  return (
    <Dialog open={open} onOpenChange={(o) => !create.isPending && onOpenChange(o)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New class</DialogTitle>
          <DialogDescription>You become its teacher. Students join with the class code.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogBody className="space-y-4">
            <Field label="Name" htmlFor="class-name">
              <Input id="class-name" autoFocus value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Description (optional)" htmlFor="class-desc">
              <Textarea id="class-desc" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
            {error && <FieldError>{error}</FieldError>}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating..." : "Create class"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
