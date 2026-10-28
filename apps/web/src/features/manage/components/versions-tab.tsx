"use client";

import { HistoryIcon } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { Hint } from "@/components/hint";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Chip } from "@/components/ui/chip";
import type { ProblemAdmin } from "@/lib/api/types";
import { formatBytes, formatDateTime } from "@/lib/format";

export function VersionsTab({ problem: p }: { problem: ProblemAdmin }) {
  return (
    <Surface>
      <SurfaceHeader
        title={
          <span className="inline-flex items-center gap-1.5">
            Versions of the tests
            <Hint term="version" />
          </span>
        }
        description="Each change to the tests is kept. Submissions remember the version they were judged on."
      />
      {p.versions.length ? (
        <ul className="divide-y divide-hairline px-5 pb-3">
          {p.versions.map((v) => (
            <li key={v.id} className="flex flex-wrap items-center gap-3 py-3 text-[13px]">
              <span className="w-24 font-semibold">Version {v.number}</span>
              {v.current && <Chip tone="primary">Current</Chip>}
              <span className="text-muted-foreground">
                {v.tests.length} tests, {formatBytes(v.package_bytes)}, {v.max_score} points
              </span>
              {v.note && <span className="text-muted-foreground">&ldquo;{v.note}&rdquo;</span>}
              <span className="ml-auto font-mono text-[11.5px] text-faint" title={v.package_sha256}>
                {v.package_sha256.slice(0, 12)}
              </span>
              <span className="text-[12px] text-muted-foreground">{formatDateTime(v.created_at)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState compact icon={HistoryIcon} title="No versions yet" description="The first version is created when you save tests or upload a package." />
      )}
    </Surface>
  );
}
