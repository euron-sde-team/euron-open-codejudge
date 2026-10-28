"use client";

import * as React from "react";
import { toast } from "sonner";

import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { errorMessage } from "@/lib/api/errors";
import type { ProblemAdmin } from "@/lib/api/types";

import { useUpdateProblem } from "../api";

const STARTER = `Describe the task in a few sentences.

## Input

The first line contains an integer $n$ ($1 \\le n \\le 10^5$).

## Output

Print one integer: the answer.
`;

export function StatementTab({ problem: p }: { problem: ProblemAdmin }) {
  const update = useUpdateProblem(p.id);
  const [text, setText] = React.useState(p.statement_md || STARTER);
  const dirty = text !== (p.statement_md || STARTER) || !p.statement_md;

  function save() {
    update.mutate(
      { statement_md: text },
      { onSuccess: () => toast.success("Statement saved."), onError: (e) => toast.error(errorMessage(e)) },
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-[13px] text-muted-foreground">
          Markdown with <code className="rounded bg-muted px-1 font-mono text-[12px]">$math$</code> and{" "}
          <code className="rounded bg-muted px-1 font-mono text-[12px]">$$display math$$</code>. Samples come from the tests and are shown
          under the statement automatically.
        </p>
        <Button className="ml-auto" disabled={update.isPending || !dirty} onClick={save}>
          {update.isPending ? "Saving..." : "Save statement"}
        </Button>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Textarea
          aria-label="Statement in Markdown"
          value={text}
          onChange={(e) => setText(e.target.value)}
          spellCheck
          className="min-h-[520px] font-mono text-[13px] leading-relaxed"
        />
        <div className="surface min-h-[520px] overflow-auto p-5" aria-label="Preview">
          <div className="mb-3 text-[11.5px] font-semibold tracking-wide text-faint uppercase">Preview</div>
          <Markdown source={text} />
        </div>
      </div>
    </div>
  );
}
