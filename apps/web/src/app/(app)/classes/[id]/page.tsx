import type { Metadata } from "next";
import { Suspense } from "react";

import { ClassScreen } from "@/features/classes/components/class-screen";

export const metadata: Metadata = { title: "Class" };

export default async function ClassPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <ClassScreen id={id} />
    </Suspense>
  );
}
