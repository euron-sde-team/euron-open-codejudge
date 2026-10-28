"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { AssessmentCreate, AssessmentUpdate } from "@/lib/api/types";
import { STALE } from "@/lib/query-keys";

const k = {
  all: ["assessments"] as const,
  list: ["assessments", "list"] as const,
  one: (id: string) => ["assessments", "detail", id] as const,
  invitations: (id: string) => ["assessments", "invitations", id] as const,
  report: (id: string, inv: string) => ["assessments", "report", id, inv] as const,
  candidate: ["candidate", "view"] as const,
};

export function useAssessments() {
  return useQuery({ queryKey: k.list, queryFn: () => unwrap(api.GET("/api/v1/assessments")), staleTime: STALE.list });
}

export function useAssessment(id: string) {
  return useQuery({
    queryKey: k.one(id),
    queryFn: () => unwrap(api.GET("/api/v1/assessments/{assessment_id}", { params: { path: { assessment_id: id } } })),
    staleTime: STALE.list,
  });
}

export function useInvitations(id: string) {
  return useQuery({
    queryKey: k.invitations(id),
    queryFn: () => unwrap(api.GET("/api/v1/assessments/{assessment_id}/invitations", { params: { path: { assessment_id: id } } })),
    staleTime: STALE.live,
    refetchInterval: 20_000,
  });
}

export function useReport(id: string, invitationId: string) {
  return useQuery({
    queryKey: k.report(id, invitationId),
    queryFn: () =>
      unwrap(api.GET("/api/v1/assessments/{assessment_id}/invitations/{invitation_id}/report", { params: { path: { assessment_id: id, invitation_id: invitationId } } })),
    staleTime: STALE.live,
  });
}

function useInvalidate() {
  const client = useQueryClient();
  return () => void client.invalidateQueries({ queryKey: k.all });
}

export function useCreateAssessment() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (body: AssessmentCreate) => unwrap(api.POST("/api/v1/assessments", { body })), onSuccess: invalidate });
}

export function useUpdateAssessment(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: AssessmentUpdate) => unwrap(api.PATCH("/api/v1/assessments/{assessment_id}", { params: { path: { assessment_id: id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeleteAssessment() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/assessments/{assessment_id}", { params: { path: { assessment_id: id } } })),
    onSuccess: invalidate,
  });
}

export function useInvite(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (candidates: { email: string; name: string }[]) =>
      unwrap(api.POST("/api/v1/assessments/{assessment_id}/invitations", { params: { path: { assessment_id: id } }, body: { candidates } })),
    onSuccess: invalidate,
  });
}

export function useResend(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (invitationId: string) =>
      unwrap(api.POST("/api/v1/assessments/{assessment_id}/invitations/{invitation_id}/resend", { params: { path: { assessment_id: id, invitation_id: invitationId } } })),
    onSuccess: invalidate,
  });
}

export function useRevoke(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (invitationId: string) =>
      unwrap(api.POST("/api/v1/assessments/{assessment_id}/invitations/{invitation_id}/revoke", { params: { path: { assessment_id: id, invitation_id: invitationId } } })),
    onSuccess: invalidate,
  });
}

// ── candidate side (the X-CodeJudge-Candidate header is added by the client) ─────────
export function useCandidateView(enabled: boolean) {
  return useQuery({
    queryKey: k.candidate,
    queryFn: () => unwrap(api.GET("/api/v1/candidate/assessment")),
    enabled,
    staleTime: STALE.live,
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useCandidateFinish() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/candidate/finish")),
    onSuccess: (view) => client.setQueryData(k.candidate, view),
  });
}

/** Paste and tab-visibility signals. Fire and forget: losing one must never block the test. */
export async function recordCandidateEvent(kind: "paste" | "tab_hidden" | "tab_visible", detail: Record<string, unknown> = {}): Promise<void> {
  try {
    await api.POST("/api/v1/candidate/events", { body: { kind, detail } });
  } catch {
    // Network blip: the signal is lost, the assessment carries on.
  }
}

export async function openCandidateSession(token: string) {
  return unwrap(api.POST("/api/v1/candidate/session", { body: { token } }));
}
