"use client";

import Editor, { type OnMount } from "@monaco-editor/react";
import { useTheme } from "next-themes";
import * as React from "react";

import { configureMonaco } from "@/lib/monaco";

export interface CodeEditorProps {
  value: string;
  onChange?: (value: string) => void;
  /** Monaco language id: python, cpp, java, javascript, plaintext. */
  language: string;
  readOnly?: boolean;
  height?: number | string;
  /** Ctrl/Cmd+Enter. */
  onRun?: () => void;
  /** Ctrl/Cmd+Shift+Enter. */
  onSubmit?: () => void;
  ariaLabel?: string;
  /** Called with the pasted text's length (assessments record pastes as a signal). */
  onPaste?: (chars: number) => void;
}

export default function CodeEditorImpl({ value, onChange, language, readOnly = false, height = 420, onRun, onSubmit, ariaLabel, onPaste }: CodeEditorProps) {
  const { resolvedTheme } = useTheme();
  const [ready] = React.useState(() => {
    configureMonaco();
    return true;
  });
  // The shortcuts call the latest handlers without re-registering the commands.
  const handlers = React.useRef({ onRun, onSubmit, onPaste });
  handlers.current = { onRun, onSubmit, onPaste };

  const mount: OnMount = (editor, monaco) => {
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => handlers.current.onRun?.());
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.Enter, () => handlers.current.onSubmit?.());
    editor.onDidPaste((e) => {
      const text = editor.getModel()?.getValueInRange(e.range) ?? "";
      handlers.current.onPaste?.(text.length);
    });
  };

  if (!ready) return null;
  return (
    <Editor
      height={height}
      language={language}
      value={value}
      theme={resolvedTheme === "dark" ? "codejudge-dark" : "codejudge-light"}
      onChange={(v) => onChange?.(v ?? "")}
      onMount={mount}
      loading={<div className="flex h-full items-center justify-center text-[13px] text-muted-foreground">Loading the editor...</div>}
      options={{
        readOnly,
        minimap: { enabled: false },
        fontFamily: "'JetBrains Mono Variable', ui-monospace, monospace",
        fontSize: 13.5,
        lineHeight: 21,
        tabSize: 4,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        padding: { top: 12, bottom: 12 },
        renderLineHighlight: readOnly ? "none" : "line",
        ariaLabel: ariaLabel ?? "Code editor",
        wordWrap: "off",
        fixedOverflowWidgets: true,
      }}
    />
  );
}
