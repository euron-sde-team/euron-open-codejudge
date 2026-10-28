// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { requestHeaders } from "@/lib/api/client";
import { candidateHeaders, CANDIDATE_HEADER, detachCandidate, getCandidateToken, looksLikeToken, setCandidateToken } from "@/lib/candidate";

const TOKEN = "AbCdEfGhIjKlMnOpQrStUvWxYz_0123456789-xyz";

afterEach(() => {
  setCandidateToken(null);
  vi.restoreAllMocks();
});

describe("candidate token", () => {
  it("is kept in this tab's session storage and survives a reload", () => {
    setCandidateToken(TOKEN);
    expect(window.sessionStorage.getItem("codejudge.candidate.v1")).toBe(TOKEN);
    detachCandidate();
    expect(getCandidateToken()).toBe(TOKEN);
  });
  it("is sent as the candidate header on every request, GET included", () => {
    setCandidateToken(TOKEN);
    expect(candidateHeaders()).toEqual({ [CANDIDATE_HEADER]: TOKEN });
    expect(requestHeaders("GET", false)[CANDIDATE_HEADER]).toBe(TOKEN);
    expect(requestHeaders("POST", true)[CANDIDATE_HEADER]).toBe(TOKEN);
  });
  it("sends nothing when there is no candidate", () => {
    setCandidateToken(null);
    expect(candidateHeaders()).toEqual({});
    expect(requestHeaders("GET", false)).toEqual({});
  });
  it("still works when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    expect(() => setCandidateToken(TOKEN)).not.toThrow();
    expect(getCandidateToken()).toBe(TOKEN);
  });
  it("accepts only plausible tokens from the address", () => {
    expect(looksLikeToken(TOKEN)).toBe(true);
    expect(looksLikeToken("short")).toBe(false);
    expect(looksLikeToken("has spaces in it and more than twenty chars")).toBe(false);
  });
});
