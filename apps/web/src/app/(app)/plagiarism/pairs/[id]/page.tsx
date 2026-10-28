import type { Metadata } from "next";

import { PairScreen } from "@/features/plagiarism/components/plagiarism-screens";

export const metadata: Metadata = { title: "Similar pair" };

export default async function PairPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PairScreen id={id} />;
}
