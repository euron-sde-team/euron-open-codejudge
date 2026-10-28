import type { Metadata } from "next";

import { ProblemEditorScreen } from "@/features/manage/components/problem-editor-screen";

export const metadata: Metadata = { title: "Edit problem" };

export default async function EditProblemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProblemEditorScreen id={id} />;
}
