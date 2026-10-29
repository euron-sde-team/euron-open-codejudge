"use client";

import { LoaderCircleIcon } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/cn";
import { verdictSpec } from "@/lib/verdicts";

/** A verdict as a chip: the short code, the full name and its meaning on hover or focus. */
export function VerdictChip({ verdict, long = false, className }: { verdict: string; long?: boolean; className?: string }) {
  const spec = verdictSpec(verdict);
  const busy = verdict === "JUDGING" || verdict === "PENDING";
  const chip = (
    <span
      data-verdict={verdict}
      className={cn(
        "inline-flex h-5 items-center gap-1 rounded-full px-2 text-[11px] leading-none font-semibold whitespace-nowrap",
        spec.className,
        className,
      )}
    >
      {busy && <LoaderCircleIcon className="size-3 animate-spin" aria-hidden />}
      {long ? spec.label : spec.short}
    </span>
  );
  return (
    <Tooltip>
      <TooltipTrigger render={<span tabIndex={0} className="inline-flex rounded-full focus-visible:outline-2 focus-visible:outline-ring" />}>
        {chip}
      </TooltipTrigger>
      <TooltipContent>
        <span className="font-semibold">{spec.label}.</span> {spec.hint}
      </TooltipContent>
    </Tooltip>
  );
}
