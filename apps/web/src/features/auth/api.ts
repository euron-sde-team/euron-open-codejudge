"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { User } from "@/lib/api/types";
import { qk, STALE } from "@/lib/query-keys";
import { isAdmin, isStaff } from "@/lib/roles";

/**
 * The signed-in user, or null for a signed-out visitor (a 401 here is not an error:
 * problems are public). Any other failure is an error the shell shows.
 */
export function useMe() {
  return useQuery({
    queryKey: qk.me,
    queryFn: async (): Promise<User | null> => {
      try {
        return await unwrap(api.GET("/api/v1/auth/me"));
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: STALE.static,
    retry: false,
  });
}

/** Role flags for the current visitor. While loading, nothing privileged is shown. */
export function usePermissions(): { user: User | null | undefined; signedIn: boolean; staff: boolean; admin: boolean } {
  const { data } = useMe();
  return { user: data, signedIn: !!data, staff: isStaff(data?.role), admin: isAdmin(data?.role) };
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => unwrap(api.POST("/api/v1/auth/login", { body })),
    onSuccess: (session) => {
      client.clear();
      client.setQueryData(qk.me, session.user);
    },
  });
}

/** Public settings the sign-in page needs (site name, whether people may sign up). */
export function usePublicSettings() {
  return useQuery({
    queryKey: qk.publicSettings,
    queryFn: () => unwrap(api.GET("/api/v1/org/public")),
    staleTime: STALE.config,
    retry: false,
  });
}

export function useSignup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; email: string; password: string }) => unwrap(api.POST("/api/v1/auth/signup", { body })),
    onSuccess: (session) => {
      client.clear();
      client.setQueryData(qk.me, session.user);
    },
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/logout")),
    onSettled: () => client.clear(),
  });
}

export function useChangePassword() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      unwrap(api.POST("/api/v1/auth/password", { body })),
    onSuccess: (session) => client.setQueryData(qk.me, session.user),
  });
}
