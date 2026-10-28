"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { ContestCreate, ContestUpdate } from "@/lib/api/types";
import { STALE } from "@/lib/query-keys";

const k = {
  all: ["contests"] as const,
  list: ["contests", "list"] as const,
  one: (ref: string) => ["contests", "detail", ref] as const,
  me: (ref: string) => ["contests", "me", ref] as const,
  board: (ref: string) => ["contests", "board", ref] as const,
  clars: (ref: string) => ["contests", "clars", ref] as const,
  problem: (ref: string, label: string) => ["contests", "problem", ref, label] as const,
  subs: (id: string, offset: number) => ["contests", "subs", id, offset] as const,
};

export function useContests() {
  return useQuery({ queryKey: k.list, queryFn: () => unwrap(api.GET("/api/v1/contests")), staleTime: STALE.list, refetchInterval: 30_000 });
}

export function useContest(ref: string) {
  return useQuery({
    queryKey: k.one(ref),
    queryFn: () => unwrap(api.GET("/api/v1/contests/{ref}", { params: { path: { ref } } })),
    staleTime: STALE.live,
    // The problem set appears at the start: refresh around phase changes.
    refetchInterval: 20_000,
  });
}

export function useMyContestStatus(ref: string, enabled: boolean) {
  return useQuery({
    queryKey: k.me(ref),
    queryFn: () => unwrap(api.GET("/api/v1/contests/{ref}/me", { params: { path: { ref } } })),
    staleTime: STALE.live,
    enabled,
    refetchInterval: 10_000,
  });
}

export function useScoreboard(ref: string, live: boolean) {
  return useQuery({
    queryKey: k.board(ref),
    queryFn: () => unwrap(api.GET("/api/v1/contests/{ref}/scoreboard", { params: { path: { ref } } })),
    staleTime: STALE.live,
    refetchInterval: live ? 10_000 : false,
  });
}

export function useClarifications(ref: string, enabled: boolean) {
  return useQuery({
    queryKey: k.clars(ref),
    queryFn: () => unwrap(api.GET("/api/v1/contests/{ref}/clarifications", { params: { path: { ref } } })),
    staleTime: STALE.live,
    enabled,
    refetchInterval: 15_000,
  });
}

export function useContestProblem(ref: string, label: string) {
  return useQuery({
    queryKey: k.problem(ref, label),
    queryFn: () => unwrap(api.GET("/api/v1/contests/{ref}/problems/{label}", { params: { path: { ref, label } } })),
    staleTime: STALE.list,
  });
}

export function useContestSubmissions(id: string, offset: number, enabled: boolean) {
  return useQuery({
    queryKey: k.subs(id, offset),
    queryFn: () => unwrap(api.GET("/api/v1/contests/{contest_id}/submissions", { params: { path: { contest_id: id }, query: { limit: 50, offset } } })),
    staleTime: STALE.live,
    enabled,
    refetchInterval: 10_000,
  });
}

function useInvalidate() {
  const client = useQueryClient();
  return () => void client.invalidateQueries({ queryKey: k.all });
}

export function useRegister(ref: string) {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: () => unwrap(api.POST("/api/v1/contests/{ref}/register", { params: { path: { ref } } })), onSuccess: invalidate });
}

export function useJoinContest() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (code: string) => unwrap(api.POST("/api/v1/contests/join", { body: { code } })), onSuccess: invalidate });
}

export function useCreateContest() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (body: ContestCreate) => unwrap(api.POST("/api/v1/contests", { body })), onSuccess: invalidate });
}

export function useUpdateContest(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: ContestUpdate) => unwrap(api.PATCH("/api/v1/contests/{contest_id}", { params: { path: { contest_id: id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeleteContest() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/contests/{contest_id}", { params: { path: { contest_id: id } } })),
    onSuccess: invalidate,
  });
}

export function useAddContestProblem(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { problem: string; label?: string | null; points?: number }) =>
      unwrap(api.POST("/api/v1/contests/{contest_id}/problems", { params: { path: { contest_id: id } }, body: { problem: body.problem, label: body.label ?? null, points: body.points ?? 100 } })),
    onSuccess: invalidate,
  });
}

export function useRemoveContestProblem(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (label: string) => unwrap(api.DELETE("/api/v1/contests/{contest_id}/problems/{label}", { params: { path: { contest_id: id, label } } })),
    onSuccess: invalidate,
  });
}

export function useReorderContest(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (labels: string[]) => unwrap(api.PUT("/api/v1/contests/{contest_id}/problems/order", { params: { path: { contest_id: id } }, body: { labels } })),
    onSuccess: invalidate,
  });
}

export function useUnfreeze(id: string) {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: () => unwrap(api.POST("/api/v1/contests/{contest_id}/unfreeze", { params: { path: { contest_id: id } } })), onSuccess: invalidate });
}

export function useAsk(ref: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { question: string; problem_label?: string | null }) =>
      unwrap(api.POST("/api/v1/contests/{ref}/clarifications", { params: { path: { ref } }, body: { question: body.question, problem_label: body.problem_label ?? null } })),
    onSuccess: invalidate,
  });
}

export function useAnnounce(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (answer: string) => unwrap(api.POST("/api/v1/contests/{contest_id}/announcements", { params: { path: { contest_id: id } }, body: { answer, public: true } })),
    onSuccess: invalidate,
  });
}

export function useAnswer(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ clarId, answer, isPublic }: { clarId: string; answer: string; isPublic: boolean }) =>
      unwrap(api.POST("/api/v1/contests/{contest_id}/clarifications/{clar_id}/answer", { params: { path: { contest_id: id, clar_id: clarId } }, body: { answer, public: isPublic } })),
    onSuccess: invalidate,
  });
}
