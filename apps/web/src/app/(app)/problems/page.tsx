import type { Metadata } from "next";
import { Suspense } from "react";

import { ProblemsScreen } from "@/features/problems/components/problems-screen";

export const metadata: Metadata = { title: "Problems" };

export default function ProblemsPage() {
  return (
    <Suspense>
      <ProblemsScreen />
    </Suspense>
  );
}
