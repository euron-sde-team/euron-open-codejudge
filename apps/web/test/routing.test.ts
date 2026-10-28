import { describe, expect, it } from "vitest";

import { HOME, loginUrl, safeNext } from "@/lib/auth-redirect";
import { activeNavItem, NAV_ITEMS, visibleTo } from "@/lib/nav";
import { contentSecurityPolicy, needsSignIn } from "@/middleware";

describe("sign-in redirects", () => {
  it("only follows same-origin paths and defaults to the problems", () => {
    expect(safeNext("/problems/sum")).toBe("/problems/sum");
    expect(safeNext("/submissions?verdict=AC")).toBe("/submissions?verdict=AC");
    expect(safeNext("https://evil.example")).toBe(HOME);
    expect(safeNext("//evil.example")).toBe(HOME);
    expect(safeNext("/\\evil.example")).toBe(HOME);
    expect(safeNext("/login")).toBe(HOME);
    expect(safeNext("/signup")).toBe(HOME);
    expect(safeNext(null)).toBe(HOME);
  });
  it("keeps where the person was", () => {
    expect(loginUrl("/submissions", "?verdict=WA")).toBe("/login?next=%2Fsubmissions%3Fverdict%3DWA");
    expect(loginUrl("/problems/sum", "", "expired")).toBe("/login?next=%2Fproblems%2Fsum&reason=expired");
    expect(loginUrl("/")).toBe("/login");
  });
  it("protects private pages and leaves problems public", () => {
    expect(needsSignIn("/submissions")).toBe(true);
    expect(needsSignIn("/manage/problems/1")).toBe(true);
    expect(needsSignIn("/admin/users")).toBe(true);
    expect(needsSignIn("/problems")).toBe(false);
    expect(needsSignIn("/problems/sum")).toBe(false);
    expect(needsSignIn("/submissionsx")).toBe(false);
  });
});

describe("content security policy", () => {
  it("allows only this origin, with workers for the editor", () => {
    const csp = contentSecurityPolicy(true);
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("worker-src 'self' blob:");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).not.toContain("unsafe-eval");
    expect(contentSecurityPolicy(false)).toContain("unsafe-eval");
  });
});

describe("navigation", () => {
  const byHref = (href: string) => NAV_ITEMS.find((i) => i.href === href)!;
  it("shows each item to the right people", () => {
    expect(visibleTo(byHref("/problems"), null)).toBe(true);
    expect(visibleTo(byHref("/submissions"), null)).toBe(false);
    expect(visibleTo(byHref("/submissions"), "student")).toBe(true);
    expect(visibleTo(byHref("/manage/problems"), "student")).toBe(false);
    expect(visibleTo(byHref("/manage/problems"), "staff")).toBe(true);
    expect(visibleTo(byHref("/admin/users"), "staff")).toBe(false);
    expect(visibleTo(byHref("/admin/users"), "admin")).toBe(true);
  });
  it("highlights the deepest matching item", () => {
    expect(activeNavItem("/problems/sum")?.href).toBe("/problems");
    expect(activeNavItem("/manage/problems/abc")?.href).toBe("/manage/problems");
    expect(activeNavItem("/nowhere")).toBeUndefined();
  });
});
