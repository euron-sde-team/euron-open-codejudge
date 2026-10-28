import type { Metadata } from "next";

import { ClassesScreen } from "@/features/classes/components/classes-screen";

export const metadata: Metadata = { title: "Classes" };

export default function ClassesPage() {
  return <ClassesScreen />;
}
