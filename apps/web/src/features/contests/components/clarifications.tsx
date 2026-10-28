"use client";

import { MegaphoneIcon, MessageCircleQuestionIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { usePermissions } from "@/features/auth/api";
import { errorMessage } from "@/lib/api/errors";
import type { Clarification, Contest } from "@/lib/api/types";
import { formatRelative } from "@/lib/format";

import { useAnnounce, useAnswer, useAsk, useClarifications } from "../api";

export function Clarifications({ contest, registered }: { contest: Contest; registered: boolean }) {
  const { staff, signedIn } = usePermissions();
  const list = useClarifications(contest.slug, signedIn);
  const ask = useAsk(contest.slug);
  const announce = useAnnounce(contest.id);
  const [question, setQuestion] = React.useState("");
  const [label, setLabel] = React.useState("");
  const [announcement, setAnnouncement] = React.useState("");
  const canAsk = registered && contest.phase === "running" && !staff;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="min-w-0 space-y-3">
        {list.isPending ? (
          <p className="text-[13px] text-muted-foreground">Loading...</p>
        ) : list.isError ? (
          <ErrorState error={list.error} title="Clarifications could not be loaded" onRetry={() => void list.refetch()} />
        ) : !list.data.length ? (
          <div className="surface">
            <EmptyState
              icon={MessageCircleQuestionIcon}
              title="No clarifications yet"
              description="If a statement is unclear, ask here. Answers to everyone's questions and announcements from the organisers appear in this list."
            />
          </div>
        ) : (
          list.data.map((c) => <ClarificationItem key={c.id} c={c} contestId={contest.id} staff={staff} />)
        )}
      </div>
      <div className="space-y-4">
        {canAsk && (
          <Surface>
            <SurfaceHeader title="Ask a question" description="Only the organisers see it. They may answer you alone or everyone." />
            <div className="space-y-3 px-5 pb-5">
              <Field label="About" htmlFor="clar-label">
                <SimpleSelect
                  id="clar-label"
                  value={label}
                  onValueChange={setLabel}
                  options={[{ value: "", label: "The contest in general" }, ...contest.problems.map((p) => ({ value: p.label, label: `${p.label}. ${p.title}` }))]}
                />
              </Field>
              <Textarea aria-label="Your question" rows={4} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What is unclear?" />
              <Button
                disabled={ask.isPending || !question.trim()}
                onClick={() =>
                  ask.mutate(
                    { question: question.trim(), problem_label: label || null },
                    {
                      onSuccess: () => {
                        setQuestion("");
                        toast.success("Sent. The answer appears in this list.");
                      },
                      onError: (e) => toast.error(errorMessage(e)),
                    },
                  )
                }
              >
                Send question
              </Button>
            </div>
          </Surface>
        )}
        {!canAsk && !staff && (
          <p className="text-[12.5px] text-muted-foreground">
            {contest.phase !== "running" ? "Questions can be asked while the contest runs." : "Register for the contest to ask questions."}
          </p>
        )}
        {staff && (
          <Surface>
            <SurfaceHeader title="Announce to everyone" description="Shown to every contestant in this list." />
            <div className="space-y-3 px-5 pb-5">
              <Textarea aria-label="Announcement" rows={3} value={announcement} onChange={(e) => setAnnouncement(e.target.value)} />
              <Button
                disabled={announce.isPending || !announcement.trim()}
                onClick={() =>
                  announce.mutate(announcement.trim(), {
                    onSuccess: () => {
                      setAnnouncement("");
                      toast.success("Announced.");
                    },
                    onError: (e) => toast.error(errorMessage(e)),
                  })
                }
              >
                <MegaphoneIcon />
                Announce
              </Button>
            </div>
          </Surface>
        )}
      </div>
    </div>
  );
}

function ClarificationItem({ c, contestId, staff }: { c: Clarification; contestId: string; staff: boolean }) {
  const answer = useAnswer(contestId);
  const [text, setText] = React.useState("");
  const [isPublic, setIsPublic] = React.useState(false);
  const isAnnouncement = !c.question && !!c.answer;
  return (
    <article className="surface p-4">
      <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
        {isAnnouncement ? <Chip tone="primary">Announcement</Chip> : c.problem_label ? <Chip tone="neutral">Problem {c.problem_label}</Chip> : <Chip tone="neutral">General</Chip>}
        {c.public && !isAnnouncement && <Chip tone="info">Answered for everyone</Chip>}
        {c.mine && <span>You asked</span>}
        {staff && c.asked_by_name && <span>Asked by {c.asked_by_name}</span>}
        <span className="ml-auto">{formatRelative(c.created_at)}</span>
      </div>
      {c.question && <p className="mt-2 text-[13.5px] whitespace-pre-wrap">{c.question}</p>}
      {c.answer ? (
        <p className={isAnnouncement ? "mt-2 text-[13.5px] whitespace-pre-wrap" : "mt-2 rounded-lg bg-muted/60 px-3 py-2 text-[13px] whitespace-pre-wrap"}>{c.answer}</p>
      ) : staff ? (
        <div className="mt-3 space-y-2">
          <Textarea aria-label="Your answer" rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="Answer" />
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
              <Switch checked={isPublic} onCheckedChange={setIsPublic} aria-label="Answer for everyone" />
              Answer for everyone
            </label>
            <Button
              size="sm"
              className="ml-auto"
              disabled={answer.isPending || !text.trim()}
              onClick={() =>
                answer.mutate({ clarId: c.id, answer: text.trim(), isPublic }, { onSuccess: () => toast.success("Answered."), onError: (e) => toast.error(errorMessage(e)) })
              }
            >
              Send answer
            </Button>
          </div>
        </div>
      ) : (
        <p className="mt-2 text-[12.5px] text-muted-foreground">Waiting for an answer from the organisers.</p>
      )}
    </article>
  );
}
