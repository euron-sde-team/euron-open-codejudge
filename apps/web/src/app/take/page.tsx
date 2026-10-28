import type { Metadata } from "next";

import { TakeScreen } from "@/features/assessments/components/take-screen";

export const metadata: Metadata = { title: "Assessment", robots: { index: false, follow: false } };

export default function TakePage() {
  return <TakeScreen />;
}
