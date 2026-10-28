import { ProblemScreen } from "@/features/problems/components/problem-screen";

export default async function ProblemPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <ProblemScreen slug={slug} />;
}
