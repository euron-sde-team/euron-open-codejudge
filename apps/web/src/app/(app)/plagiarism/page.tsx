import type { Metadata } from "next";

import { PlagiarismScreen } from "@/features/plagiarism/components/plagiarism-screens";

export const metadata: Metadata = { title: "Plagiarism" };

export default function PlagiarismPage() {
  return <PlagiarismScreen />;
}
