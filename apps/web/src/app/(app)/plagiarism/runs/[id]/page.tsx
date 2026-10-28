import type { Metadata } from "next";

import { RunScreen } from "@/features/plagiarism/components/plagiarism-screens";

export const metadata: Metadata = { title: "Plagiarism check" };

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RunScreen id={id} />;
}
