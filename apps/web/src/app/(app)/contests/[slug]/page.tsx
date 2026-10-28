import type { Metadata } from "next";
import { Suspense } from "react";

import { ContestScreen } from "@/features/contests/components/contest-screen";

export const metadata: Metadata = { title: "Contest" };

export default async function ContestPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return (
    <Suspense>
      <ContestScreen slug={slug} />
    </Suspense>
  );
}
