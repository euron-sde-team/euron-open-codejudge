"use client";

import { useParams, useRouter } from "next/navigation";
import * as React from "react";

import { looksLikeToken, setCandidateToken } from "@/lib/candidate";

/**
 * The invitation link. The token moves into this tab's session storage and out of the
 * address bar (so it is not left in history or shown on screen), then the assessment opens.
 */
export default function TakeTokenPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  React.useEffect(() => {
    const token = decodeURIComponent(params.token ?? "");
    setCandidateToken(looksLikeToken(token) ? token : null);
    router.replace("/take");
  }, [params.token, router]);
  return <p className="p-10 text-center text-[13px] text-muted-foreground">Opening your assessment...</p>;
}
