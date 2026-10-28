"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import { STALE } from "@/lib/query-keys";

export function useOverview(days: number) {
  return useQuery({
    queryKey: ["analytics", "overview", days],
    queryFn: () => unwrap(api.GET("/api/v1/analytics/overview", { params: { query: { days } } })),
    staleTime: STALE.list,
    placeholderData: keepPreviousData,
  });
}

export function useProblemStats(ref: string, days: number) {
  return useQuery({
    queryKey: ["analytics", "problem", ref, days],
    queryFn: () => unwrap(api.GET("/api/v1/analytics/problems/{ref}", { params: { path: { ref }, query: { days } } })),
    staleTime: STALE.list,
    placeholderData: keepPreviousData,
  });
}

export function useMyProgress(days: number) {
  return useQuery({
    queryKey: ["analytics", "me", days],
    queryFn: () => unwrap(api.GET("/api/v1/analytics/me", { params: { query: { days } } })),
    staleTime: STALE.list,
    placeholderData: keepPreviousData,
  });
}
