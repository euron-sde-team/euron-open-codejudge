"use client";

import { LogInIcon, PlayIcon, RotateCcwIcon, SendIcon, TerminalSquareIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { CodeEditor } from "@/components/code-editor";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Button, buttonVariants } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { SimpleSelect } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { HintBox } from "@/features/hints/hint-box";
import { useLiveSubmission, useRun, useSubmit } from "@/features/submissions/api";
import { ResultPanel } from "@/features/submissions/components/result-panel";
import { errorMessage } from "@/lib/api/errors";
import type { Language, Problem } from "@/lib/api/types";
import { loginUrl } from "@/lib/auth-redirect";
import { loadDraft, loadLanguage, saveDraft, saveLanguage } from "@/lib/drafts";
import { formatTime } from "@/lib/verdicts";

type Context = "practice" | "contest" | "assignment" | "assessment";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
const MOD = isMac ? "Cmd" : "Ctrl";

export function Workspace({
  problem,
  signedIn,
  context = "practice",
  contextId,
  closedReason,
  hints = true,
  onPaste,
  onSubmitted,
}: {
  problem: Problem;
  /** Signed in, or an interview candidate: may run and submit. */
  signedIn: boolean;
  context?: Context;
  contextId?: string;
  /** Why running and submitting are closed (the contest ended, the assignment is shut). */
  closedReason?: string | null;
  /** Offer AI hints when the server allows them here. */
  hints?: boolean;
  onPaste?: (chars: number) => void;
  onSubmitted?: () => void;
}) {
  const pathname = usePathname();
  const languages = problem.languages;
  const draftScope = contextId ? `${problem.slug}@${contextId}` : problem.slug;
  const closed = !!closedReason;
  const [language, setLanguage] = React.useState<Language | undefined>(undefined);
  const [code, setCode] = React.useState("");
  const [customOpen, setCustomOpen] = React.useState(false);
  const [customInput, setCustomInput] = React.useState(problem.samples[0]?.input ?? "");
  const [currentId, setCurrentId] = React.useState<string | null>(null);
  const [resetOpen, setResetOpen] = React.useState(false);
  const run = useRun();
  const submit = useSubmit();
  const { live, submission } = useLiveSubmission(currentId);
  const busy = run.isPending || submit.isPending || (!!submission && submission.status !== "done");

  // Pick the language last used for this problem (else the first), and its draft.
  React.useEffect(() => {
    if (!languages.length) return;
    const saved = loadLanguage(draftScope);
    const lang = languages.find((l) => l.id === saved) ?? languages[0];
    setLanguage(lang);
    setCode(loadDraft(draftScope, lang!.id) ?? lang!.template);
  }, [draftScope, languages]);

  // Save the draft as it is typed (cheap: a localStorage write per change).
  React.useEffect(() => {
    if (language) saveDraft(draftScope, language.id, code, language.template);
  }, [draftScope, language, code]);

  function changeLanguage(id: string) {
    const lang = languages.find((l) => l.id === id);
    if (!lang || lang.id === language?.id) return;
    setLanguage(lang);
    saveLanguage(draftScope, lang.id);
    setCode(loadDraft(draftScope, lang.id) ?? lang.template);
  }

  function doRun(custom: boolean) {
    if (!language || busy || !signedIn || closed) return;
    run.mutate(
      {
        problem: problem.slug,
        language: language.id,
        source: code,
        input: custom ? customInput : null,
        context,
        context_id: contextId ?? null,
      },
      { onSuccess: (s) => setCurrentId(s.id), onError: (e) => toast.error(errorMessage(e)) },
    );
  }

  function doSubmit() {
    if (!language || busy || !signedIn || closed) return;
    if (!code.trim()) {
      toast.error("Write some code first: the editor is empty.");
      return;
    }
    submit.mutate(
      { problem: problem.slug, language: language.id, source: code, context, context_id: contextId ?? null },
      {
        onSuccess: (s) => {
          setCurrentId(s.id);
          toast.success("Submitted. Judging on every test now.");
          onSubmitted?.();
        },
        onError: (e) => toast.error(errorMessage(e)),
      },
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div className="surface overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 bg-muted/50 px-3 py-2">
          <SimpleSelect
            aria-label="Language"
            size="sm"
            className="w-48"
            value={language?.id ?? ""}
            onValueChange={changeLanguage}
            options={languages.map((l) => ({ value: l.id, label: l.name }))}
          />
          {language?.time_limit_ms != null && (
            <span className="text-[12px] text-muted-foreground">Time limit {formatTime(language.time_limit_ms)}</span>
          )}
          <Tooltip>
            <TooltipTrigger
              render={
                <Button variant="subtle" size="icon-sm" className="ml-auto" aria-label="Reset to the template" onClick={() => setResetOpen(true)} />
              }
            >
              <RotateCcwIcon />
            </TooltipTrigger>
            <TooltipContent>Reset to the template</TooltipContent>
          </Tooltip>
        </div>
        <CodeEditor
          value={code}
          onChange={setCode}
          language={language?.monaco ?? "plaintext"}
          height={460}
          onRun={() => doRun(customOpen)}
          onSubmit={doSubmit}
          onPaste={onPaste}
          ariaLabel={`Your ${language?.name ?? ""} solution`}
        />
        {customOpen && (
          <div className="bg-muted/40 px-3 py-3">
            <label htmlFor="custom-input" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
              Your input
            </label>
            <Textarea
              id="custom-input"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              rows={4}
              spellCheck={false}
              className="font-mono text-[12.5px]"
            />
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 px-3 py-2.5">
          {closed ? (
            <span className="text-[13px] text-muted-foreground">{closedReason}</span>
          ) : signedIn ? (
            <>
              <Button variant="secondary" size="sm" disabled={busy || !language} onClick={() => doRun(customOpen)}>
                <PlayIcon />
                {customOpen ? "Run on my input" : "Run samples"}
              </Button>
              <Button variant="subtle" size="sm" aria-pressed={customOpen} onClick={() => setCustomOpen((o) => !o)}>
                <TerminalSquareIcon />
                {customOpen ? "Use the samples" : "Custom input"}
              </Button>
              <span className="hidden text-[11.5px] text-faint md:inline">
                {MOD}+Enter runs, {MOD}+Shift+Enter submits
              </span>
              <Button size="sm" className="ml-auto" disabled={busy || !language} onClick={doSubmit}>
                <SendIcon />
                {submit.isPending ? "Submitting..." : "Submit"}
              </Button>
            </>
          ) : (
            <>
              <span className="text-[13px] text-muted-foreground">Sign in to run your code and submit it for a verdict.</span>
              <Link href={loginUrl(pathname)} className={buttonVariants({ size: "sm", className: "ml-auto" })}>
                <LogInIcon />
                Sign in
              </Link>
            </>
          )}
        </div>
      </div>
      {submission && (
        <div className="surface p-4">
          <ResultPanel submission={submission} live={live} showLink={context !== "assessment"} />
        </div>
      )}
      {hints && signedIn && !closed && language && context !== "assessment" && context !== "contest" && (
        <HintBox problem={problem.slug} context={context} contextId={contextId} language={language.id} source={code} />
      )}
      <ConfirmDialog
        open={resetOpen}
        onOpenChange={setResetOpen}
        title="Reset to the template?"
        description="Your code for this language is replaced by the starting template. This cannot be undone."
        confirmLabel="Reset"
        destructive
        onConfirm={() => {
          if (language) setCode(language.template);
          setResetOpen(false);
        }}
      />
    </div>
  );
}
