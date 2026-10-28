"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import { qk, STALE } from "@/lib/query-keys";

/** Deployment info and judge capacity (staff and admins). */
export function useSystemInfo() {
  return useQuery({
    queryKey: qk.system,
    queryFn: () => unwrap(api.GET("/api/v1/system")),
    staleTime: STALE.live,
    refetchInterval: 15_000,
  });
}

/** The judge queue: workers online, jobs waiting and in progress. */
export function useQueueStatus() {
  return useQuery({
    queryKey: qk.queue,
    queryFn: () => unwrap(api.GET("/api/v1/judge/queue")),
    staleTime: STALE.live,
    refetchInterval: 10_000,
  });
}
