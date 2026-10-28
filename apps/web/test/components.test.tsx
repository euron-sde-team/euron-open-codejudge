// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown, safeUrl } from "@/components/markdown";
import { TooltipProvider } from "@/components/ui/tooltip";
import { VerdictChip } from "@/components/verdict-chip";
import { explain } from "@/features/submissions/components/result-panel";
import { TestsTable } from "@/features/submissions/components/tests-table";
import type { Submission } from "@/lib/api/types";

describe("markdown statements", () => {
  it("renders math and code", () => {
    const { container } = render(<Markdown source={"Sum $a + b$.\n\n```\nprint(1)\n```"} />);
    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.querySelector("pre code")?.textContent).toContain("print(1)");
  });
  it("never renders raw HTML from the statement", () => {
    const { container } = render(<Markdown source={'Hi <script>alert(1)</script><img src=x onerror="alert(1)"><iframe src="https://x.test"></iframe>'} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("iframe")).toBeNull();
    expect(container.querySelector("img[onerror]")).toBeNull();
  });
  it("drops javascript: and data: links", () => {
    const { container } = render(<Markdown source={"[x](javascript:alert(1)) [y](data:text/html,hi) [z](https://ok.example)"} />);
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href") ?? "");
    expect(hrefs.some((h) => h.startsWith("javascript"))).toBe(false);
    expect(hrefs.some((h) => h.startsWith("data:"))).toBe(false);
    expect(hrefs).toContain("https://ok.example");
    expect(safeUrl("mailto:a@b.test")).toBe("mailto:a@b.test");
    expect(safeUrl("vbscript:x")).toBe("");
  });
});

describe("verdicts on screen", () => {
  it("shows a verdict's short code", () => {
    render(
      <TooltipProvider>
        <VerdictChip verdict="TLE" />
      </TooltipProvider>,
    );
    expect(screen.getByText("TLE")).toBeTruthy();
  });
  it("lets samples open but never shows anything for hidden tests", () => {
    render(
      <TooltipProvider>
        <TestsTable
          tests={[
            { name: "sample/1", group: "sample", verdict: "WA", time_ms: 3, memory_kb: 900, output: "4\n", message: "token 1: expected 3, got 4" },
            { name: "secret/1", group: "secret", verdict: "AC", time_ms: 5, memory_kb: 900, output: null, message: null },
          ]}
        />
      </TooltipProvider>,
    );
    expect(screen.getByRole("button", { name: /Sample 1/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Hidden 1/ })).toBeNull();
    expect(screen.getByText("Hidden 1")).toBeTruthy();
  });
  it("says what to do next for each verdict", () => {
    const base = { context: "practice", run_input: null } as unknown as Submission;
    expect(explain({ ...base, verdict: "TLE" })).toMatch(/faster algorithm/);
    expect(explain({ ...base, verdict: "IE" })).toMatch(/not your program/);
    expect(explain({ ...base, context: "run", verdict: "AC" } as Submission)).toMatch(/Submit it/);
  });
});
