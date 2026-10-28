import type { Metadata } from "next";

import { SubmissionScreen } from "@/features/submissions/components/submission-screen";

export const metadata: Metadata = { title: "Submission" };

export default async function SubmissionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SubmissionScreen id={id} />;
}
