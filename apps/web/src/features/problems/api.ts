"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { Difficulty } from "@/lib/api/types";
import { qk, STALE } from "@/lib/query-keys";

export interface ProblemFilters {
  q?: string;
  tag?: string;
  difficulty?: Difficulty | "";
  status?: "draft" | "published" | "";
  limit?: number;
  offset?: number;
}

export function useLanguages() {
  return useQuery({
    queryKey: qk.languages,
    queryFn: () => unwrap(api.GET("/api/v1/languages")),
    staleTime: STALE.static,
  });
}

export function useTags() {
  return useQuery({ queryKey: qk.tags, queryFn: () => unwrap(api.GET("/api/v1/problem-tags")), staleTime: STALE.config });
}

export function useProblems(filters: ProblemFilters) {
  return useQuery({
    queryKey: qk.problems(filters),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/problems", {
          params: {
            query: {
              q: filters.q || null,
              tag: filters.tag || null,
              difficulty: filters.difficulty || null,
              status: filters.status || null,
              limit: filters.limit ?? 50,
              offset: filters.offset ?? 0,
            },
          },
        }),
      ),
    staleTime: STALE.list,
    placeholderData: keepPreviousData,
  });
}

export function useProblem(ref: string) {
  return useQuery({
    queryKey: qk.problem(ref),
    queryFn: () => unwrap(api.GET("/api/v1/problems/{ref}", { params: { path: { ref } } })),
    staleTime: STALE.list,
  });
}
