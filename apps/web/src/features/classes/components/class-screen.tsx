"use client";

import { ArrowLeftIcon, ClipboardListIcon, FileQuestionIcon, PlusIcon, RefreshCwIcon, Trash2Icon, UserPlusIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/confirm-dialog";
import { CopyButton } from "@/components/copy-button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Button, buttonVariants } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePermissions } from "@/features/auth/api";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { Assignment, ClassRoom } from "@/lib/api/types";
import { STATUS_TEXT } from "@/lib/classes";
import { formatDateTime } from "@/lib/format";
import { formatScore } from "@/lib/verdicts";

import { useAddMember, useClass, useClassAssignments, useCreateAssignment, useDeleteClass, useMembers, useRemoveMember, useRotateCode, useUpdateClass } from "../api";
import { AssignmentFields, assignmentPayload, emptyAssignment, type AssignmentValues } from "./assignment-form";

type Tab = "assignments" | "roster" | "settings";

const STATUS_TONE: Record<string, "info" | "success" | "warning" | "neutral"> = { upcoming: "info", open: "success", late: "warning", closed: "neutral" };

export function ClassScreen({ id }: { id: string }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { staff } = usePermissions();
  const klass = useClass(id);
  const tab = (params.get("tab") as Tab | null) ?? "assignments";

  if (klass.isPending) return <Skeleton className="h-64 w-full" />;
  if (klass.isError) {
    if (klass.error instanceof ApiError && (klass.error.status === 404 || klass.error.status === 403)) {
      return (
        <EmptyState
          icon={FileQuestionIcon}
          title="This class is not available"
          description="You may not be a member. Join it with the code your teacher gave you."
          action={
            <Link href="/classes" className={buttonVariants()}>
              My classes
            </Link>
          }
        />
      );
    }
    return <ErrorState error={klass.error} title="The class could not be loaded" onRetry={() => void klass.refetch()} />;
  }
  const c = klass.data;
  const teacher = c.my_role === "teacher" || staff;

  return (
    <div className="space-y-5">
      <Link href="/classes" className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" aria-hidden />
        Classes
      </Link>
      <header className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.02em]">{c.name}</h1>
            {c.archived && <Chip tone="neutral">Archived</Chip>}
          </div>
          {c.description && <p className="mt-1 text-[13px] text-muted-foreground">{c.description}</p>}
          <p className="mt-1 text-[12px] text-muted-foreground">
            {c.students} students, {c.teachers} teacher{c.teachers === 1 ? "" : "s"}
          </p>
        </div>
        {teacher && c.join_code && <JoinCode klass={c} />}
      </header>
      {teacher ? (
        <Tabs value={tab} onValueChange={(v) => router.replace(v === "assignments" ? pathname : `${pathname}?tab=${String(v)}`, { scroll: false })}>
          <TabsList>
            <TabsTrigger value="assignments">Assignments</TabsTrigger>
            <TabsTrigger value="roster">Roster</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>
          <TabsContent value="assignments">
            <Assignments klass={c} teacher />
          </TabsContent>
          <TabsContent value="roster">
            <Roster klass={c} />
          </TabsContent>
          <TabsContent value="settings">
            <ClassSettings klass={c} />
          </TabsContent>
        </Tabs>
      ) : (
        <Assignments klass={c} teacher={false} />
      )}
    </div>
  );
}

function JoinCode({ klass: c }: { klass: ClassRoom }) {
  const rotate = useRotateCode(c.id);
  return (
    <div className="surface flex items-center gap-2 px-3 py-2">
      <span className="text-[12px] text-muted-foreground">Class code</span>
      <code className="font-mono text-[14px] font-semibold tracking-wider">{c.join_code}</code>
      <CopyButton value={c.join_code ?? ""} iconOnly variant="ghost" label="Copy class code" />
      <Button
        variant="subtle"
        size="icon-sm"
        aria-label="Make a new code (the old one stops working)"
        title="Make a new code (the old one stops working)"
        disabled={rotate.isPending}
        onClick={() => rotate.mutate(undefined, { onSuccess: () => toast.success("New code made. The old one no longer works."), onError: (e) => toast.error(errorMessage(e)) })}
      >
        <RefreshCwIcon />
      </Button>
    </div>
  );
}

function Assignments({ klass: c, teacher }: { klass: ClassRoom; teacher: boolean }) {
  const list = useClassAssignments(c.id);
  const [creating, setCreating] = React.useState(false);
  return (
    <div className="space-y-3">
      {teacher && (
        <div className="flex justify-end">
          <Button onClick={() => setCreating(true)}>
            <PlusIcon />
            New assignment
          </Button>
        </div>
      )}
      {list.isPending ? (
        <p className="text-[13px] text-muted-foreground">Loading...</p>
      ) : list.isError ? (
        <ErrorState error={list.error} title="Assignments could not be loaded" onRetry={() => void list.refetch()} />
      ) : !list.data.length ? (
        <div className="surface">
          <EmptyState
            icon={ClipboardListIcon}
            title="No assignments yet"
            description={teacher ? "An assignment is a set of problems with an opening time, a due time and a late policy. Create the first one." : "Your teacher has not set any work yet. Assignments appear here with their due dates."}
            action={
              teacher && (
                <Button onClick={() => setCreating(true)}>
                  <PlusIcon />
                  New assignment
                </Button>
              )
            }
          />
        </div>
      ) : (
        <ul className="surface divide-y divide-hairline overflow-hidden">
          {list.data.map((a) => (
            <AssignmentRow key={a.id} a={a} teacher={teacher} />
          ))}
        </ul>
      )}
      <CreateAssignmentDialog classId={c.id} open={creating} onOpenChange={setCreating} />
    </div>
  );
}

function AssignmentRow({ a, teacher }: { a: Assignment; teacher: boolean }) {
  return (
    <li>
      <Link href={`/assignments/${a.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-muted/50 focus-visible:bg-muted/60 focus-visible:outline-none sm:px-5">
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14px] font-medium">{a.title}</span>
          <span className="text-[12px] text-muted-foreground">
            {a.status === "upcoming" ? `Opens ${formatDateTime(a.opens_at)}` : `Due ${formatDateTime(a.my_due_at)}`}, {a.problems.length} problem{a.problems.length === 1 ? "" : "s"}
          </span>
        </span>
        <Chip tone={STATUS_TONE[a.status] ?? "neutral"}>{STATUS_TEXT[a.status] ?? a.status}</Chip>
        {!teacher && <span className="tabular w-24 text-right text-[12.5px] font-semibold">{formatScore(a.my_total ?? 0, a.total_points)}</span>}
      </Link>
    </li>
  );
}

function CreateAssignmentDialog({ classId, open, onOpenChange }: { classId: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const create = useCreateAssignment(classId);
  const [values, setValues] = React.useState<AssignmentValues>(emptyAssignment);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (open) {
      setValues(emptyAssignment());
      setError(null);
    }
  }, [open]);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    const p = assignmentPayload(values);
    if (!p.ok) return setError(p.error);
    create.mutate(p.body, {
      onSuccess: (a) => {
        toast.success("Assignment created.");
        onOpenChange(false);
        router.push(`/assignments/${a.id}`);
      },
      onError: (err) => setError(errorMessage(err)),
    });
  }
  return (
    <Dialog open={open} onOpenChange={(o) => !create.isPending && onOpenChange(o)}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New assignment</DialogTitle>
          <DialogDescription>Times are in your time zone. Students see it from the opening time.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogBody className="space-y-4">
            <AssignmentFields values={values} onChange={setValues} />
            {error && <FieldError>{error}</FieldError>}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating..." : "Create assignment"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Roster({ klass: c }: { klass: ClassRoom }) {
  const members = useMembers(c.id, true);
  const add = useAddMember(c.id);
  const remove = useRemoveMember(c.id);
  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState<"student" | "teacher">("student");
  const [removing, setRemoving] = React.useState<{ id: string; name: string } | null>(null);
  return (
    <div className="space-y-4">
      <Surface>
        <SurfaceHeader title="Add someone" description="They need an account on this server. Students can also join themselves with the class code." />
        <div className="flex flex-wrap items-end gap-2 px-5 pb-5">
          <Field label="Email" htmlFor="m-email" className="min-w-56 flex-1">
            <Input id="m-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Role" htmlFor="m-role" className="w-36">
            <SimpleSelect
              id="m-role"
              value={role}
              onValueChange={(v) => setRole(v === "teacher" ? "teacher" : "student")}
              options={[
                { value: "student", label: "Student" },
                { value: "teacher", label: "Teacher" },
              ]}
            />
          </Field>
          <Button
            disabled={add.isPending || !email.trim()}
            onClick={() =>
              add.mutate(
                { email: email.trim(), role },
                {
                  onSuccess: () => {
                    setEmail("");
                    toast.success("Added to the class.");
                  },
                  onError: (e) => toast.error(errorMessage(e)),
                },
              )
            }
          >
            <UserPlusIcon />
            Add
          </Button>
        </div>
      </Surface>
      <Surface>
        <SurfaceHeader title="Members" />
        {members.isPending ? (
          <p className="px-5 pb-4 text-[13px] text-muted-foreground">Loading...</p>
        ) : members.isError ? (
          <ErrorState compact error={members.error} title="Members could not be loaded" onRetry={() => void members.refetch()} />
        ) : !members.data.length ? (
          <p className="px-5 pb-4 text-[13px] text-muted-foreground">Nobody yet. Share the class code, or add people above.</p>
        ) : (
          <ul className="divide-y divide-hairline px-5 pb-3">
            {members.data.map((m) => (
              <li key={m.user_id} className="flex items-center gap-3 py-2.5 text-[13px]">
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{m.name}</span>
                  <span className="block truncate text-[12px] text-muted-foreground">{m.email}</span>
                </span>
                {m.role === "teacher" && <Chip tone="primary">Teacher</Chip>}
                <Button variant="subtle" size="icon-sm" aria-label={`Remove ${m.name}`} onClick={() => setRemoving({ id: m.user_id, name: m.name })}>
                  <Trash2Icon />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Surface>
      <ConfirmDialog
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        title={`Remove ${removing?.name ?? "this person"} from the class?`}
        description="They lose access to its assignments. Their submissions are kept, and they can rejoin with the code."
        confirmLabel="Remove"
        destructive
        pending={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing.id, { onSuccess: () => setRemoving(null), onError: (e) => toast.error(errorMessage(e)) })}
      />
    </div>
  );
}

function ClassSettings({ klass: c }: { klass: ClassRoom }) {
  const router = useRouter();
  const update = useUpdateClass(c.id);
  const del = useDeleteClass();
  const [name, setName] = React.useState(c.name);
  const [description, setDescription] = React.useState(c.description);
  const [deleting, setDeleting] = React.useState(false);
  return (
    <Surface className="max-w-2xl space-y-4 p-5">
      <Field label="Name" htmlFor="cs-name">
        <Input id="cs-name" value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
      <Field label="Description" htmlFor="cs-desc">
        <Textarea id="cs-desc" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>
      <label className="flex items-center gap-2 text-[13px]">
        <Switch
          checked={c.archived}
          onCheckedChange={(v) => update.mutate({ archived: v }, { onSuccess: () => toast.success(v ? "Class archived." : "Class restored."), onError: (e) => toast.error(errorMessage(e)) })}
          aria-label="Archived"
        />
        Archived (kept for reference)
      </label>
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={update.isPending || !name.trim()}
          onClick={() => update.mutate({ name: name.trim(), description: description.trim() }, { onSuccess: () => toast.success("Saved."), onError: (e) => toast.error(errorMessage(e)) })}
        >
          Save
        </Button>
        <Button variant="destructive-soft" className="ml-auto" onClick={() => setDeleting(true)}>
          <Trash2Icon />
          Delete class
        </Button>
      </div>
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title="Delete this class?"
        description="The class, its roster, assignments and gradebooks are deleted for good. Archive it instead to keep the records."
        confirmLabel="Delete class"
        destructive
        pending={del.isPending}
        onConfirm={() =>
          del.mutate(c.id, {
            onSuccess: () => {
              toast.success("Class deleted.");
              router.replace("/classes");
            },
            onError: (e) => toast.error(errorMessage(e)),
          })
        }
      />
    </Surface>
  );
}
