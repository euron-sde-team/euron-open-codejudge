"use client";

import * as React from "react";

import { formatCountdown } from "@/lib/time";

/** Now, re-rendered every second (or slower) while mounted. */
export function useNow(intervalMs = 1000): Date {
  const [now, setNow] = React.useState(() => new Date());
  React.useEffect(() => {
    const t = setInterval(() => setNow(new Date()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

/** "Ends in 1:04:05", ticking. Calls onElapsed once when it reaches zero. */
export function Countdown({ to, label, onElapsed, className }: { to: string | Date; label?: string; onElapsed?: () => void; className?: string }) {
  const now = useNow();
  const ms = new Date(to).getTime() - now.getTime();
  const fired = React.useRef(false);
  React.useEffect(() => {
    if (ms <= 0 && !fired.current) {
      fired.current = true;
      onElapsed?.();
    }
  }, [ms, onElapsed]);
  return (
    <span className={className} role="timer" aria-live="off">
      {label && <span className="text-muted-foreground">{label} </span>}
      <span className="tabular font-semibold">{formatCountdown(ms)}</span>
    </span>
  );
}
