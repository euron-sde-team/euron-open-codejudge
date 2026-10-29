"use client";

import { useLanguages } from "@/features/problems/api";

/** A language's display name ("Python 3") for its id ("python3"); the id until loaded. */
export function LanguageName({ id }: { id: string }) {
  const languages = useLanguages();
  return <>{languages.data?.find((l) => l.id === id)?.name ?? id}</>;
}
