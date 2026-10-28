"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";

import type { CodeEditorProps } from "./editor-impl";

/** The code editor, loaded in the browser only (Monaco needs the DOM and web workers). */
export const CodeEditor = dynamic<CodeEditorProps>(() => import("./editor-impl"), {
  ssr: false,
  loading: () => <Skeleton className="h-[420px] w-full rounded-none" />,
});

export type { CodeEditorProps };
