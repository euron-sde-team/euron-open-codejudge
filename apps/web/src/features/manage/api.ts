"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, rawJson, unwrap } from "@/lib/api/client";
import type { ImportResult, ProblemCreate, ProblemUpdate, ReferenceIn, Version, VersionCreate } from "@/lib/api/types";
import { qk, STALE } from "@/lib/query-keys";

/** The staff view of one problem: versions, tests metadata, references, publish blockers. */
export function useProblemAdmin(id: string) {
  return useQuery({
    queryKey: qk.problemAdmin(id),
    queryFn: () => unwrap(api.GET("/api/v1/problems/{ref}/admin", { params: { path: { ref: id } } })),
    staleTime: STALE.live,
    // While a reference solution is being judged, keep the blockers fresh.
    refetchInterval: (query) =>
      query.state.data?.references.some((r) => r.last_status && r.last_status !== "done") ? 2000 : false,
  });
}

function useInvalidateProblem() {
  const client = useQueryClient();
  return (id?: string) => {
    void client.invalidateQueries({ queryKey: qk.problemsAll });
    if (id) void client.invalidateQueries({ queryKey: qk.problemAdmin(id) });
  };
}

export function useCreateProblem() {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: (body: ProblemCreate) => unwrap(api.POST("/api/v1/problems", { body })),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateProblem(id: string) {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: (body: ProblemUpdate) => unwrap(api.PATCH("/api/v1/problems/{problem_id}", { params: { path: { problem_id: id } }, body })),
    onSuccess: () => invalidate(id),
  });
}

export function useDeleteProblem() {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/v1/problems/{problem_id}", { params: { path: { problem_id: id } } })),
    onSuccess: () => invalidate(),
  });
}

export function usePublish(id: string) {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: (publish: boolean) =>
      publish
        ? unwrap(api.POST("/api/v1/problems/{problem_id}/publish", { params: { path: { problem_id: id } } }))
        : unwrap(api.POST("/api/v1/problems/{problem_id}/unpublish", { params: { path: { problem_id: id } } })),
    onSuccess: () => invalidate(id),
  });
}

export function useCreateVersion(id: string) {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: (body: VersionCreate) => unwrap(api.POST("/api/v1/problems/{problem_id}/versions", { params: { path: { problem_id: id } }, body })),
    onSuccess: () => invalidate(id),
  });
}

/** New tests (and checker) from a Kattis package zip; the statement and limits stay. */
export function useUploadPackage(id: string) {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return rawJson<Version>("POST", `/api/v1/problems/${id}/package`, form);
    },
    onSuccess: () => invalidate(id),
  });
}

/** A new problem from a Kattis package zip. */
export function useImportProblem() {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: ({ file, slug }: { file: File; slug?: string }) => {
      const form = new FormData();
      form.append("file", file);
      if (slug) form.append("slug", slug);
      return rawJson<ImportResult>("POST", "/api/v1/problems/import", form);
    },
    onSuccess: () => invalidate(),
  });
}

export function useAddReference(id: string) {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: (body: ReferenceIn) => unwrap(api.POST("/api/v1/problems/{problem_id}/references", { params: { path: { problem_id: id } }, body })),
    onSuccess: () => invalidate(id),
  });
}

export function useRemoveReference(id: string) {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: (refId: string) =>
      unwrap(api.DELETE("/api/v1/problems/{problem_id}/references/{ref_id}", { params: { path: { problem_id: id, ref_id: refId } } })),
    onSuccess: () => invalidate(id),
  });
}

export function useJudgeReferences(id: string) {
  const invalidate = useInvalidateProblem();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/problems/{problem_id}/references/judge", { params: { path: { problem_id: id } } })),
    onSuccess: () => invalidate(id),
  });
}

export function useRejudgeProblem(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/problems/{problem_id}/rejudge", { params: { path: { problem_id: id } } })),
    onSuccess: () => void client.invalidateQueries({ queryKey: qk.submissionsAll }),
  });
}

/** The text of one test file (staff only). */
export async function fetchTestPart(problemId: string, name: string, part: "input" | "answer"): Promise<string> {
  const res = await fetch(`/api/v1/problems/${problemId}/tests/${name}?part=${part}`, { credentials: "same-origin" });
  if (!res.ok) throw new Error(`Could not read ${name} (${part}): HTTP ${res.status}`);
  return res.text();
}
