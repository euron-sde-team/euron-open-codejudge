import type { Metadata } from "next";

import { AssessmentScreen } from "@/features/assessments/components/assessment-screen";

export const metadata: Metadata = { title: "Assessment" };

export default async function AssessmentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AssessmentScreen id={id} />;
}
