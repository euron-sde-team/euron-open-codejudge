"use client";

import { ActivityIcon, CpuIcon, DatabaseIcon, FileCode2Icon, HourglassIcon, ListChecksIcon, UsersIcon, type LucideIcon } from "lucide-react";

import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Stat } from "@/components/stat";
import { Surface, SurfaceHeader } from "@/components/surface";
import { Chip } from "@/components/ui/chip";
import { formatNumber } from "@/lib/format";

import { useQueueStatus, useSystemInfo } from "../api";

function Row({ label, icon: Icon, value }: { label: string; icon?: LucideIcon; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2 text-[13px]">
      <span className="inline-flex items-center gap-1.5 text-muted-foreground">
        {Icon && <Icon className="size-3.5" aria-hidden />}
        {label}
      </span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

export function SystemScreen() {
  const info = useSystemInfo();
  const queue = useQueueStatus();
  const q = queue.data;
  const noJudge = q && q.workers === 0;

  return (
    <>
      <PageHeader
        title="System"
        description="Judge capacity and how this deployment is configured. Refreshes every few seconds."
      />
      {noJudge && (
        <div role="status" className="mb-4 rounded-xl bg-warning-soft px-4 py-3 text-[13px] text-warning">
          No judge worker is online, so submissions wait in the queue. Start one with{" "}
          <code className="rounded bg-card/60 px-1 font-mono text-[12px]">make up</code> (or scale the judge service), then
          submissions are judged in order.
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Judges online" icon={CpuIcon} value={q ? formatNumber(q.workers) : "n/a"} tone={noJudge ? "warn" : "good"} loading={queue.isPending} />
        <Stat label="Waiting" icon={HourglassIcon} value={q ? formatNumber(q.waiting) : "n/a"} loading={queue.isPending} detail="Jobs no judge has taken yet" />
        <Stat label="Being judged" icon={ActivityIcon} value={q ? formatNumber(q.in_progress) : "n/a"} loading={queue.isPending} detail="Taken, not yet reported" />
        <Stat label="Submissions" icon={ListChecksIcon} value={info.data ? formatNumber(info.data.submissions) : "n/a"} loading={info.isPending} />
      </div>
      {queue.isError && <ErrorState className="mt-4" compact error={queue.error} title="The judge queue could not be read" onRetry={() => void queue.refetch()} />}

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Surface>
          <SurfaceHeader title="Deployment" description="Where data lives and how secrets are kept." />
          <div className="divide-y divide-hairline px-5 pb-3">
            {info.isError ? (
              <ErrorState compact error={info.error} title="System details could not be read" onRetry={() => void info.refetch()} />
            ) : info.data ? (
              <>
                <Row label="Version" value={`v${info.data.version}`} />
                <Row label="Environment" value={info.data.environment} />
                <Row label="Test data and exports" value={info.data.storage === "s3" ? "S3" : "Local disk"} />
                <Row label="Secret sealing" value={info.data.key_mode === "kms" ? "KMS" : "Local master key"} />
                <Row label="Cache" value={info.data.cache === "redis" ? "Redis" : "In process"} />
                <Row label="Mail" value={info.data.mail} />
                <Row label="Job queue (Redis)" value={info.data.redis ? <Chip tone="success">Connected</Chip> : <Chip tone="warning">Unreachable</Chip>} />
              </>
            ) : (
              <div className="py-6 text-[13px] text-muted-foreground">Loading...</div>
            )}
          </div>
        </Surface>
        <Surface>
          <SurfaceHeader title="Content" description="What this server holds." />
          <div className="divide-y divide-hairline px-5 pb-3">
            {info.data && (
              <>
                <Row label="Problems" icon={FileCode2Icon} value={formatNumber(info.data.problems)} />
                <Row label="Users" icon={UsersIcon} value={formatNumber(info.data.users)} />
                <Row label="Submissions" icon={DatabaseIcon} value={formatNumber(info.data.submissions)} />
                <Row label="Languages" value={info.data.languages.join(", ")} />
              </>
            )}
          </div>
        </Surface>
      </div>
    </>
  );
}
