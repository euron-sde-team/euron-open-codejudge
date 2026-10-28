/**
 * The interview candidate's token: from the invitation link, kept in this tab's
 * sessionStorage (it dies with the tab) and sent as X-CodeJudge-Candidate on every
 * candidate request. Storage can be blocked, so it is also kept in memory.
 */

export const CANDIDATE_HEADER = "x-codejudge-candidate";
const KEY = "codejudge.candidate.v1";

let current: string | null = null;

export function setCandidateToken(token: string | null): void {
  current = token;
  try {
    if (typeof window === "undefined") return;
    if (token) window.sessionStorage.setItem(KEY, token);
    else window.sessionStorage.removeItem(KEY);
  } catch {
    // Storage blocked: the token still lives in memory for this page.
  }
}

export function getCandidateToken(): string | null {
  if (current) return current;
  try {
    current = typeof window !== "undefined" ? window.sessionStorage.getItem(KEY) : null;
  } catch {
    current = null;
  }
  return current;
}

/** Forget the token in memory only (leaving the candidate pages), keeping it for a reload. */
export function detachCandidate(): void {
  current = null;
}

/** The header to add to a request, when a candidate is active. */
export function candidateHeaders(token: string | null = getCandidateToken()): Record<string, string> {
  return token ? { [CANDIDATE_HEADER]: token } : {};
}

/** A plausible invitation token from the URL (the API checks it for real). */
export function looksLikeToken(value: string): boolean {
  return /^[A-Za-z0-9_-]{20,200}$/.test(value);
}
