"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { PlagiarismScope } from "@/lib/api/types";
import { STALE } from "@/lib/query-keys";

const k = {
  all: ["plagiarism"] as const,
  runs: ["plagiarism", "runs"] as const,
  run: (id: string) => ["plagiarism", "run", id] as const,
  pair: (id: string) => ["plagiarism", "pair", id] as const,
};

export function useRuns() {
  return useQuery({
    queryKey: k.runs,
    queryFn: () => unwrap(api.GET("/api/v1/plagiarism/runs", { params: { query: { limit: 100 } } })),
    staleTime: STALE.live,
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "queued" || r.status === "running") ? 3000 : false),
  });
}

export function useRun(id: string) {
  return useQuery({
    queryKey: k.run(id),
    queryFn: () => unwrap(api.GET("/api/v1/plagiarism/runs/{run_id}", { params: { path: { run_id: id } } })),
    staleTime: STALE.live,
    refetchInterval: (q) => (q.state.data && (q.state.data.status === "queued" || q.state.data.status === "running") ? 3000 : false),
  });
}

export function usePair(id: string) {
  return useQuery({
    queryKey: k.pair(id),
    queryFn: () => unwrap(api.GET("/api/v1/plagiarism/pairs/{pair_id}", { params: { path: { pair_id: id } } })),
    staleTime: STALE.static,
  });
}

export function useStartRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { scope: PlagiarismScope; scope_id: string; threshold: number }) => unwrap(api.POST("/api/v1/plagiarism/runs", { body })),
    onSuccess: () => void client.invalidateQueries({ queryKey: k.all }),
  });
}
