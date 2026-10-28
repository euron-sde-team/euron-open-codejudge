import type { Metadata } from "next";

import { ReportScreen } from "@/features/assessments/components/report-screen";

export const metadata: Metadata = { title: "Candidate report" };

export default async function ReportPage({ params }: { params: Promise<{ id: string; invitationId: string }> }) {
  const { id, invitationId } = await params;
  return <ReportScreen assessmentId={id} invitationId={invitationId} />;
}
