import type { Metadata } from "next";

import { ProgressScreen } from "@/features/analytics/components/analytics-screens";

export const metadata: Metadata = { title: "My progress" };

export default function ProgressPage() {
  return <ProgressScreen />;
}
