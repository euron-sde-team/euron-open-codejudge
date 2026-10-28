// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { draftKey, loadDraft, loadLanguage, saveDraft, saveLanguage } from "@/lib/drafts";

afterEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("drafts", () => {
  it("keeps code per problem and language", () => {
    saveDraft("sum", "python3", "print(1)");
    saveDraft("sum", "cpp17", "int main(){}");
    expect(loadDraft("sum", "python3")).toBe("print(1)");
    expect(loadDraft("sum", "cpp17")).toBe("int main(){}");
    expect(loadDraft("other", "python3")).toBeNull();
  });
  it("forgets a draft that is just the template or empty", () => {
    saveDraft("sum", "python3", "print(1)");
    saveDraft("sum", "python3", "TEMPLATE", "TEMPLATE");
    expect(loadDraft("sum", "python3")).toBeNull();
    saveDraft("sum", "python3", "print(1)");
    saveDraft("sum", "python3", "   ");
    expect(window.localStorage.getItem(draftKey("sum", "python3"))).toBeNull();
  });
  it("remembers the language last used", () => {
    saveLanguage("sum", "java21");
    expect(loadLanguage("sum")).toBe("java21");
  });
  it("never throws when storage is blocked or full", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    expect(() => saveDraft("sum", "python3", "x")).not.toThrow();
    expect(() => saveLanguage("sum", "python3")).not.toThrow();
    expect(loadDraft("sum", "python3")).toBeNull();
    expect(loadLanguage("sum")).toBeNull();
  });
});
