import type { Metadata } from "next";

import { ContestsScreen } from "@/features/contests/components/contests-screen";

export const metadata: Metadata = { title: "Contests" };

export default function ContestsPage() {
  return <ContestsScreen />;
}
