"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import { STALE } from "@/lib/query-keys";

export type HintContext = "practice" | "assignment" | "contest" | "assessment";

const statusKey = (problem: string, context: HintContext) => ["hints", "status", problem, context] as const;

/** Whether a hint can be asked for this problem here, and how many remain. */
export function useHintStatus(problem: string, context: HintContext, enabled: boolean) {
  return useQuery({
    queryKey: statusKey(problem, context),
    queryFn: () => unwrap(api.GET("/api/v1/hints/status", { params: { query: { problem, context } } })),
    staleTime: STALE.config,
    enabled,
    retry: false,
  });
}

export function useAskHint(problem: string, context: HintContext) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { language: string; source: string; question?: string | null; context_id?: string | null }) =>
      unwrap(
        api.POST("/api/v1/hints", {
          body: { problem, language: body.language, source: body.source, question: body.question ?? null, context, context_id: body.context_id ?? null },
        }),
      ),
    onSettled: () => void client.invalidateQueries({ queryKey: statusKey(problem, context) }),
  });
}
