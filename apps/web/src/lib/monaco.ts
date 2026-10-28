"use client";

/**
 * Monaco, bundled with the app (no CDN): only the editor core and the four languages the
 * judge runs, with the editor worker bundled as a separate chunk. Imported only from the
 * client-side editor component.
 */
import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import "monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution";
import "monaco-editor/esm/vs/basic-languages/java/java.contribution";
import "monaco-editor/esm/vs/basic-languages/javascript/javascript.contribution";
import "monaco-editor/esm/vs/basic-languages/python/python.contribution";

let configured = false;

export function configureMonaco(): typeof monaco {
  if (configured) return monaco;
  configured = true;
  window.MonacoEnvironment = {
    getWorker: () => new Worker(new URL("monaco-editor/esm/vs/editor/editor.worker.js", import.meta.url), { type: "module" }),
  };
  // Colours mirror the app's tokens (globals.css): the editor is a code slab in the page.
  monaco.editor.defineTheme("codejudge-light", {
    base: "vs",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#ffffff",
      "editor.lineHighlightBackground": "#f5f6f9",
      "editorLineNumber.foreground": "#a3aab8",
      "editorCursor.foreground": "#0f766e",
      "editor.selectionBackground": "#c9ece6",
    },
  });
  monaco.editor.defineTheme("codejudge-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#13161d",
      "editor.lineHighlightBackground": "#181b24",
      "editorLineNumber.foreground": "#5d6576",
      "editorCursor.foreground": "#2dd4bf",
      "editor.selectionBackground": "#134e4a",
    },
  });
  loader.config({ monaco });
  return monaco;
}
