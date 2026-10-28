import type { Metadata } from "next";

import { AnalyticsScreen } from "@/features/analytics/components/analytics-screens";

export const metadata: Metadata = { title: "Analytics" };

export default function AnalyticsPage() {
  return <AnalyticsScreen />;
}
