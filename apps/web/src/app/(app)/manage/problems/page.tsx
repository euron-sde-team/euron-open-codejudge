import type { Metadata } from "next";

import { ManageProblemsScreen } from "@/features/manage/components/manage-problems-screen";

export const metadata: Metadata = { title: "Problem editor" };

export default function ManageProblemsPage() {
  return <ManageProblemsScreen />;
}
