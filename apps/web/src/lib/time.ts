/** Countdowns and time windows. */

/** "2d 3h", "3:04:05", "4:05", "0:09"; never negative. */
export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const days = Math.floor(total / 86_400);
  const hours = Math.floor((total % 86_400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (days > 0) return `${days}d ${hours}h`;
  const mm = String(minutes).padStart(hours > 0 ? 2 : 1, "0");
  const ss = String(seconds).padStart(2, "0");
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

export type Window = "before" | "during" | "after";

/** Where now falls relative to a start and an end. */
export function windowOf(start: string | Date, end: string | Date, now: Date = new Date()): Window {
  const s = new Date(start).getTime();
  const e = new Date(end).getTime();
  const t = now.getTime();
  if (t < s) return "before";
  if (t >= e) return "after";
  return "during";
}

/** The next moment that matters and what it is called. */
export function nextDeadline(start: string, end: string, now: Date = new Date()): { label: string; ms: number } | null {
  const w = windowOf(start, end, now);
  if (w === "before") return { label: "Starts in", ms: new Date(start).getTime() - now.getTime() };
  if (w === "during") return { label: "Ends in", ms: new Date(end).getTime() - now.getTime() };
  return null;
}

/** An ISO time as the value of an <input type="datetime-local"> in this browser's zone. */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** A datetime-local value back to an ISO time with a zone (the API requires one). */
export function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}
