import type { Metadata } from "next";

import { AssessmentsScreen } from "@/features/assessments/components/assessments-screen";

export const metadata: Metadata = { title: "Assessments" };

export default function AssessmentsPage() {
  return <AssessmentsScreen />;
}
