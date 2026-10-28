import type { Metadata } from "next";

import { ProblemAnalyticsScreen } from "@/features/analytics/components/analytics-screens";

export const metadata: Metadata = { title: "Problem analytics" };

export default async function ProblemAnalyticsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <ProblemAnalyticsScreen slug={slug} />;
}
