"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import { api, unwrap } from "@/lib/api/client";
import type { RunCreate, Submission, SubmissionCreate } from "@/lib/api/types";
import { getCandidateToken } from "@/lib/candidate";
import { applyLiveEvent, parseLiveEvent, type LiveEvent } from "@/lib/live";
import { qk, STALE } from "@/lib/query-keys";

export interface SubmissionFilters {
  problem?: string;
  verdict?: string;
  userId?: string;
  mine?: boolean;
  limit?: number;
  offset?: number;
}

export function useSubmissions(filters: SubmissionFilters, enabled = true) {
  return useQuery({
    queryKey: qk.submissions(filters),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/submissions", {
          params: {
            query: {
              problem: filters.problem || null,
              verdict: filters.verdict || null,
              user_id: filters.userId || null,
              mine: filters.mine ?? false,
              limit: filters.limit ?? 50,
              offset: filters.offset ?? 0,
            },
          },
        }),
      ),
    staleTime: STALE.live,
    placeholderData: keepPreviousData,
    enabled,
    // Keep refreshing while anything on the page is still being judged.
    refetchInterval: (query) => (query.state.data?.items.some((s) => s.status !== "done") ? 3000 : false),
  });
}

export function useSubmission(id: string | null, poll = false) {
  return useQuery({
    queryKey: qk.submission(id ?? ""),
    queryFn: () => unwrap(api.GET("/api/v1/submissions/{submission_id}", { params: { path: { submission_id: id ?? "" } } })),
    enabled: !!id,
    staleTime: STALE.live,
    refetchInterval: (query) => (poll && query.state.data?.status !== "done" ? 1500 : false),
  });
}

export function useSubmit() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmissionCreate) => unwrap(api.POST("/api/v1/submissions", { body })),
    onSuccess: (s) => {
      client.setQueryData(qk.submission(s.id), s);
      void client.invalidateQueries({ queryKey: qk.submissionsAll });
    },
  });
}

export function useRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: RunCreate) => unwrap(api.POST("/api/v1/runs", { body })),
    onSuccess: (s) => client.setQueryData(qk.submission(s.id), s),
  });
}

export function useRejudge() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { ids: string[]; latest_version?: boolean }) =>
      unwrap(api.POST("/api/v1/submissions/rejudge", { body: { ids: body.ids, latest_version: body.latest_version ?? false } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.submissionsAll }),
  });
}

/**
 * Follow one submission live: progress from the event stream, then the full result once
 * the verdict is in. If the stream cannot be opened the result is polled instead, so a
 * proxy that drops event streams only makes the view slower, never stuck.
 */
export function useLiveSubmission(id: string | null): {
  live: LiveEvent | null;
  submission: Submission | undefined;
  error: unknown;
  refetch: () => void;
} {
  const client = useQueryClient();
  const [polling, setPolling] = React.useState(false);
  const query = useSubmission(id, polling);
  const [live, setLive] = React.useState<LiveEvent | null>(null);
  const done = query.data?.status === "done";

  React.useEffect(() => {
    setLive(null);
    setPolling(false);
    if (!id || typeof window === "undefined") return;
    // EventSource cannot send the candidate header, so candidates poll for the verdict.
    if (typeof EventSource === "undefined" || getCandidateToken()) {
      setPolling(true);
      return;
    }
    let closed = false;
    const source = new EventSource(`/api/v1/submissions/${id}/events`, { withCredentials: true });
    source.onmessage = (msg) => {
      const event = parseLiveEvent(String(msg.data));
      if (!event || closed) return;
      setLive((cur) => applyLiveEvent(cur, event));
      if (event.status === "done") {
        source.close();
        void client.invalidateQueries({ queryKey: qk.submission(id) });
      }
    };
    source.onerror = () => {
      // The stream ended or could not start: poll for the verdict instead.
      source.close();
      if (!closed) setPolling(true);
    };
    return () => {
      closed = true;
      source.close();
    };
  }, [id, client]);

  React.useEffect(() => {
    if (done) setLive((cur) => (cur ? { ...cur, status: "done", verdict: query.data?.verdict ?? cur.verdict } : cur));
  }, [done, query.data?.verdict]);

  return { live, submission: query.data, error: query.error, refetch: () => void query.refetch() };
}
