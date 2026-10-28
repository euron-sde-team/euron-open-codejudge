"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { AssignmentCreate, AssignmentUpdate } from "@/lib/api/types";
import { STALE } from "@/lib/query-keys";

const k = {
  all: ["classes"] as const,
  list: ["classes", "list"] as const,
  one: (id: string) => ["classes", "detail", id] as const,
  members: (id: string) => ["classes", "members", id] as const,
  assignments: (id: string) => ["classes", "assignments", id] as const,
  mine: ["classes", "my-assignments"] as const,
  assignment: (id: string) => ["classes", "assignment", id] as const,
  gradebook: (id: string) => ["classes", "gradebook", id] as const,
  problem: (id: string, ref: string) => ["classes", "problem", id, ref] as const,
};

export function useClasses() {
  return useQuery({ queryKey: k.list, queryFn: () => unwrap(api.GET("/api/v1/classes")), staleTime: STALE.list });
}

export function useClass(id: string) {
  return useQuery({
    queryKey: k.one(id),
    queryFn: () => unwrap(api.GET("/api/v1/classes/{class_id}", { params: { path: { class_id: id } } })),
    staleTime: STALE.list,
    enabled: !!id,
  });
}

export function useMembers(id: string, enabled: boolean) {
  return useQuery({
    queryKey: k.members(id),
    queryFn: () => unwrap(api.GET("/api/v1/classes/{class_id}/members", { params: { path: { class_id: id } } })),
    staleTime: STALE.list,
    enabled,
  });
}

export function useClassAssignments(id: string) {
  return useQuery({
    queryKey: k.assignments(id),
    queryFn: () => unwrap(api.GET("/api/v1/classes/{class_id}/assignments", { params: { path: { class_id: id } } })),
    staleTime: STALE.list,
  });
}

export function useMyAssignments() {
  return useQuery({ queryKey: k.mine, queryFn: () => unwrap(api.GET("/api/v1/my/assignments")), staleTime: STALE.list });
}

export function useAssignment(id: string) {
  return useQuery({
    queryKey: k.assignment(id),
    queryFn: () => unwrap(api.GET("/api/v1/assignments/{assignment_id}", { params: { path: { assignment_id: id } } })),
    staleTime: STALE.live,
  });
}

export function useGradebook(id: string, enabled: boolean) {
  return useQuery({
    queryKey: k.gradebook(id),
    queryFn: () => unwrap(api.GET("/api/v1/assignments/{assignment_id}/gradebook", { params: { path: { assignment_id: id } } })),
    staleTime: STALE.live,
    enabled,
    refetchInterval: 30_000,
  });
}

export function useAssignmentProblem(id: string, ref: string) {
  return useQuery({
    queryKey: k.problem(id, ref),
    queryFn: () => unwrap(api.GET("/api/v1/assignments/{assignment_id}/problems/{ref}", { params: { path: { assignment_id: id, ref } } })),
    staleTime: STALE.list,
  });
}

function useInvalidate() {
  const client = useQueryClient();
  return () => void client.invalidateQueries({ queryKey: k.all });
}

export function useCreateClass() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (body: { name: string; description: string }) => unwrap(api.POST("/api/v1/classes", { body })), onSuccess: invalidate });
}

export function useJoinClass() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (code: string) => unwrap(api.POST("/api/v1/classes/join", { body: { code } })), onSuccess: invalidate });
}

export function useUpdateClass(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { name?: string | null; description?: string | null; archived?: boolean | null }) =>
      unwrap(api.PATCH("/api/v1/classes/{class_id}", { params: { path: { class_id: id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeleteClass() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/classes/{class_id}", { params: { path: { class_id: id } } })), onSuccess: invalidate });
}

export function useRotateCode(id: string) {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: () => unwrap(api.POST("/api/v1/classes/{class_id}/rotate-code", { params: { path: { class_id: id } } })), onSuccess: invalidate });
}

export function useAddMember(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { email: string; role: "teacher" | "student" }) => unwrap(api.POST("/api/v1/classes/{class_id}/members", { params: { path: { class_id: id } }, body })),
    onSuccess: invalidate,
  });
}

export function useRemoveMember(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (userId: string) => unwrap(api.DELETE("/api/v1/classes/{class_id}/members/{user_id}", { params: { path: { class_id: id, user_id: userId } } })),
    onSuccess: invalidate,
  });
}

export function useCreateAssignment(classId: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: AssignmentCreate) => unwrap(api.POST("/api/v1/classes/{class_id}/assignments", { params: { path: { class_id: classId } }, body })),
    onSuccess: invalidate,
  });
}

export function useUpdateAssignment(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: AssignmentUpdate) => unwrap(api.PATCH("/api/v1/assignments/{assignment_id}", { params: { path: { assignment_id: id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeleteAssignment() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/assignments/{assignment_id}", { params: { path: { assignment_id: id } } })),
    onSuccess: invalidate,
  });
}

export function useExtension(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { user_id: string; due_at: string }) => unwrap(api.PUT("/api/v1/assignments/{assignment_id}/extensions", { params: { path: { assignment_id: id } }, body })),
    onSuccess: invalidate,
  });
}
