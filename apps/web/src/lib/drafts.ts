/**
 * Per-problem drafts in this browser: the code for each language and the language last
 * used. Storage can be missing or throw (private windows, blocked site data), so every
 * access is guarded and the editor simply starts from the template then.
 */

const PREFIX = "codejudge.draft.v1";
const MAX_CHARS = 200_000;

function storage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function draftKey(problem: string, language: string): string {
  return `${PREFIX}:${problem}:${language}`;
}

function languageKey(problem: string): string {
  return `${PREFIX}:${problem}:language`;
}

export function loadDraft(problem: string, language: string): string | null {
  try {
    return storage()?.getItem(draftKey(problem, language)) ?? null;
  } catch {
    return null;
  }
}

/** Save the code; a draft equal to the template (untouched) is removed instead. */
export function saveDraft(problem: string, language: string, code: string, template = ""): void {
  try {
    const s = storage();
    if (!s) return;
    if (!code.trim() || code === template) s.removeItem(draftKey(problem, language));
    else s.setItem(draftKey(problem, language), code.slice(0, MAX_CHARS));
  } catch {
    // Quota exceeded or storage blocked: the draft just is not kept.
  }
}

export function loadLanguage(problem: string): string | null {
  try {
    return storage()?.getItem(languageKey(problem)) ?? null;
  } catch {
    return null;
  }
}

export function saveLanguage(problem: string, language: string): void {
  try {
    storage()?.setItem(languageKey(problem), language);
  } catch {
    // Not kept; harmless.
  }
}
