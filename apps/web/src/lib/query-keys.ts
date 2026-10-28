/**
 * Query keys in one place, so invalidation after a mutation names exactly what it
 * touched.
 */
export const qk = {
  me: ["auth", "me"] as const,
  publicSettings: ["settings", "public"] as const,
  system: ["system"] as const,
  queue: ["judge", "queue"] as const,
  users: ["users"] as const,
  languages: ["languages"] as const,
  tags: ["problems", "tags"] as const,
  problems: (filters: object) => ["problems", "list", filters] as const,
  problemsAll: ["problems"] as const,
  problem: (ref: string) => ["problems", "detail", ref] as const,
  problemAdmin: (id: string) => ["problems", "admin", id] as const,
  submissions: (filters: object) => ["submissions", "list", filters] as const,
  submissionsAll: ["submissions"] as const,
  submission: (id: string) => ["submissions", "detail", id] as const,
  audit: (action?: string) => ["audit", { action }] as const,
};

/** staleTime per kind of data, chosen deliberately. */
export const STALE = {
  live: 5_000,
  list: 15_000,
  config: 30_000,
  static: 5 * 60_000,
} as const;
