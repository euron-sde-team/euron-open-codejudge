"use client";

import { CalendarClockIcon, KeyRoundIcon, PlusIcon, TrophyIcon, UsersIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Countdown } from "@/components/countdown";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { TableSkeleton } from "@/components/table-skeleton";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Field, FieldError } from "@/components/ui/label";
import { usePermissions } from "@/features/auth/api";
import { errorMessage } from "@/lib/api/errors";
import type { ContestSummary } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { isSlug, slugify } from "@/lib/slug";

import { useContests, useCreateContest, useJoinContest } from "../api";
import { ContestFields, contestPayload, emptyContest, type ContestFormValues } from "./contest-form";

const GROUPS: { phase: ContestSummary["phase"]; title: string }[] = [
  { phase: "running", title: "Running now" },
  { phase: "upcoming", title: "Upcoming" },
  { phase: "ended", title: "Past" },
];

export function ContestsScreen() {
  const { signedIn, staff } = usePermissions();
  const list = useContests();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [joinOpen, setJoinOpen] = React.useState(false);

  return (
    <>
      <PageHeader
        title="Contests"
        description="Timed rounds with a live scoreboard. Register for one, or join a private contest with its code."
        actions={
          <div className="flex gap-2">
            {signedIn && (
              <Button variant="secondary" onClick={() => setJoinOpen(true)}>
                <KeyRoundIcon />
                Join with a code
              </Button>
            )}
            {staff && (
              <Button onClick={() => setCreateOpen(true)}>
                <PlusIcon />
                New contest
              </Button>
            )}
          </div>
        }
      />
      {list.isPending ? (
        <div className="surface">
          <TableSkeleton rows={5} cols={3} />
        </div>
      ) : list.isError ? (
        <ErrorState error={list.error} title="Contests could not be loaded" onRetry={() => void list.refetch()} />
      ) : !list.data.length ? (
        <div className="surface">
          <EmptyState
            icon={TrophyIcon}
            title="No contests yet"
            description={
              staff
                ? "A contest is a set of problems with a start and an end, scored ICPC or IOI style. Create one and add problems to it."
                : "Contests appear here when staff schedule them. A private contest needs its join code."
            }
            action={
              staff ? (
                <Button onClick={() => setCreateOpen(true)}>
                  <PlusIcon />
                  New contest
                </Button>
              ) : (
                signedIn && (
                  <Button variant="secondary" onClick={() => setJoinOpen(true)}>
                    Join with a code
                  </Button>
                )
              )
            }
          />
        </div>
      ) : (
        <div className="space-y-6">
          {GROUPS.map((g) => {
            const items = list.data.filter((c) => c.phase === g.phase);
            if (!items.length) return null;
            return (
              <section key={g.phase} aria-label={g.title}>
                <h2 className="mb-2 text-[13px] font-semibold text-muted-foreground">{g.title}</h2>
                <ul className="surface divide-y divide-hairline overflow-hidden">
                  {items.map((c) => (
                    <ContestRow key={c.id} contest={c} />
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
      <CreateContestDialog open={createOpen} onOpenChange={setCreateOpen} />
      <JoinDialog open={joinOpen} onOpenChange={setJoinOpen} />
    </>
  );
}

function ContestRow({ contest: c }: { contest: ContestSummary }) {
  return (
    <li>
      <Link href={`/contests/${c.slug}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-muted/50 focus-visible:bg-muted/60 focus-visible:outline-none sm:px-5">
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14px] font-medium">{c.title}</span>
          <span className="mt-0.5 flex flex-wrap items-center gap-x-3 text-[12px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <CalendarClockIcon className="size-3.5" aria-hidden />
              {formatDateTime(c.starts_at)} to {formatDateTime(c.ends_at)}
            </span>
            <span className="inline-flex items-center gap-1">
              <UsersIcon className="size-3.5" aria-hidden />
              {c.participants} registered
            </span>
          </span>
        </span>
        <Chip tone="neutral">{c.format.toUpperCase()}</Chip>
        {c.visibility === "private" && <Chip tone="neutral">Private</Chip>}
        {c.registered && <Chip tone="success">Registered</Chip>}
        {c.phase === "running" && <Countdown to={c.ends_at} label="Ends in" className="text-[12.5px]" />}
        {c.phase === "upcoming" && <Countdown to={c.starts_at} label="Starts in" className="text-[12.5px]" />}
      </Link>
    </li>
  );
}

function CreateContestDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const create = useCreateContest();
  const [values, setValues] = React.useState<ContestFormValues>(emptyContest);
  const [slugTouched, setSlugTouched] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setValues(emptyContest());
      setSlugTouched(false);
      setError(null);
    }
  }, [open]);

  function change(v: ContestFormValues) {
    if (v.slug !== values.slug) setSlugTouched(true);
    setValues(!slugTouched && v.title !== values.title && v.slug === values.slug ? { ...v, slug: slugify(v.title) } : v);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const p = contestPayload(values);
    if (!p.ok) return setError(p.error);
    if (!isSlug(values.slug)) return setError("The slug needs 3 to 64 lower case letters, digits or hyphens.");
    create.mutate(
      { ...p.body, slug: values.slug },
      {
        onSuccess: (c) => {
          toast.success("Contest created. Add problems to it next.");
          onOpenChange(false);
          router.push(`/contests/${c.slug}?tab=manage`);
        },
        onError: (err) => setError(errorMessage(err)),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !create.isPending && onOpenChange(o)}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New contest</DialogTitle>
          <DialogDescription>Times are in your time zone. You add problems after creating it.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogBody className="space-y-4">
            <ContestFields values={values} onChange={change} withSlug />
            {error && <FieldError>{error}</FieldError>}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating..." : "Create contest"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function JoinDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const join = useJoinContest();
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
    if (code.trim().length < 4) return setError("Enter the code the organiser gave you.");
    join.mutate(code.trim(), {
      onSuccess: (c) => {
        toast.success(`You are registered for ${c.title}.`);
        onOpenChange(false);
        router.push(`/contests/${c.slug}`);
      },
      onError: (err) => setError(errorMessage(err)),
    });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !join.isPending && onOpenChange(o)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Join a contest</DialogTitle>
          <DialogDescription>Private contests are joined with the code the organiser shares.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-col" noValidate>
          <DialogBody>
            <Field label="Join code" htmlFor="join-code">
              <Input id="join-code" autoFocus autoComplete="off" className="font-mono uppercase" value={code} onChange={(e) => setCode(e.target.value)} />
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
