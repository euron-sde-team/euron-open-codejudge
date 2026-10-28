import type { Metadata } from "next";

import { ContestProblemScreen } from "@/features/contests/components/contest-problem-screen";

export const metadata: Metadata = { title: "Contest problem" };

export default async function ContestProblemPage({ params }: { params: Promise<{ slug: string; label: string }> }) {
  const { slug, label } = await params;
  return <ContestProblemScreen slug={slug} label={label} />;
}
