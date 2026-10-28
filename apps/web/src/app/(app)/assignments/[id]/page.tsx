import type { Metadata } from "next";

import { AssignmentScreen } from "@/features/classes/components/assignment-screen";

export const metadata: Metadata = { title: "Assignment" };

export default async function AssignmentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AssignmentScreen id={id} />;
}
