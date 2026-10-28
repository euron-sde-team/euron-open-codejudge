import type { Metadata } from "next";

import { AssignmentProblemScreen } from "@/features/classes/components/assignment-problem-screen";

export const metadata: Metadata = { title: "Assignment problem" };

export default async function AssignmentProblemPage({ params }: { params: Promise<{ id: string; slug: string }> }) {
  const { id, slug } = await params;
  return <AssignmentProblemScreen id={id} slug={slug} />;
}
