import type { Metadata } from "next";
import { Suspense } from "react";

import { SubmissionsScreen } from "@/features/submissions/components/submissions-screen";

export const metadata: Metadata = { title: "Submissions" };

export default function SubmissionsPage() {
  return (
    <Suspense>
      <SubmissionsScreen />
    </Suspense>
  );
}
