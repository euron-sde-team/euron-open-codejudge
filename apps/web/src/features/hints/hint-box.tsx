"use client";

import { LightbulbIcon, SparklesIcon } from "lucide-react";
import * as React from "react";

import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/api/errors";

import { useAskHint, useHintStatus, type HintContext } from "./api";

/**
 * Optional AI hints. The button appears only when the server says hints are available
 * here; otherwise one quiet line says why (off, not in this context, or used up).
 */
export function HintBox({
  problem,
  context,
  contextId,
  language,
  source,
}: {
  problem: string;
  context: HintContext;
  contextId?: string;
  language: string;
  source: string;
}) {
  const status = useHintStatus(problem, context, true);
  const ask = useAskHint(problem, context);
  const [question, setQuestion] = React.useState("");
  const [hint, setHint] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  if (!status.data) return null;
  const s = status.data;
  if (!s.available) {
    // Hints switched off entirely say nothing; a limit or a context rule says why.
    if (!s.reason) return null;
    return (
      <p className="flex items-start gap-2 px-1 text-[12.5px] text-muted-foreground">
        <LightbulbIcon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        {s.reason}
      </p>
    );
  }

  function request() {
    setError(null);
    ask.mutate(
      { language, source, question: question.trim() || null, context_id: contextId ?? null },
      { onSuccess: (h) => setHint(h.hint), onError: (e) => setError(errorMessage(e)) },
    );
  }

  return (
    <div className="surface space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <SparklesIcon className="size-4 text-primary" aria-hidden />
        <span className="text-[13px] font-semibold">Stuck? Ask for a hint</span>
        <span className="text-[12px] text-muted-foreground">
          {s.remaining ?? 0} of {s.limit ?? 0} left for this problem
        </span>
      </div>
      <p className="text-[12.5px] text-muted-foreground">
        The tutor sees the statement, your code and your last result, never the hidden tests. It nudges you; it does not write the solution.
      </p>
      <div className="flex flex-wrap gap-2">
        <Input
          aria-label="What are you stuck on? (optional)"
          placeholder="What are you stuck on? (optional)"
          className="h-8 min-w-0 flex-1"
          value={question}
          maxLength={1000}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <Button size="sm" variant="secondary" disabled={ask.isPending || (s.remaining ?? 0) <= 0} onClick={request}>
          <LightbulbIcon />
          {ask.isPending ? "Thinking..." : "Get a hint"}
        </Button>
      </div>
      {error && <p className="text-[12.5px] text-danger">{error}</p>}
      {hint && (
        <div className="rounded-lg bg-primary-soft px-4 py-3" aria-live="polite">
          <Markdown source={hint} className="text-[13px]" />
        </div>
      )}
    </div>
  );
}
