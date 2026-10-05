export interface UserInfo {
  user_id: number;
  name: string;
  created_at: string;
}
export interface UsageRecord {
  usage_id: number;
  usage: number;
  timestamp: string;
}

export const presets = [
  { value: "15m", label: "15m", duration: 15 * 60_000 },
  { value: "30m", label: "30m", duration: 30 * 60_000 },
  { value: "1h", label: "1h", duration: 60 * 60_000 },
  { value: "3h", label: "3h", duration: 3 * 60 * 60_000 },
  { value: "12h", label: "12h", duration: 12 * 60 * 60_000 },
  { value: "1d", label: "1d", duration: 24 * 60 * 60_000 },
  { value: "7d", label: "7d", duration: 7 * 24 * 60 * 60_000 },
] as const;
export type Preset = (typeof presets)[number]["value"];
export type TimeFilter =
  | { kind: "preset"; value: Preset }
  | { kind: "custom"; start: string; end: string };

export function historyPath(filter: TimeFilter): string {
  const params =
    filter.kind === "preset"
      ? new URLSearchParams({ timeframe: filter.value })
      : new URLSearchParams({ start_date: filter.start, end_date: filter.end });
  return `/api/user/actions?${params}`;
}

export function parseCustomRange(start: string, end: string): TimeFilter {
  const from = new Date(start);
  const to = new Date(end);
  if (
    !start ||
    !end ||
    !Number.isFinite(from.getTime()) ||
    !Number.isFinite(to.getTime())
  ) {
    throw new Error("Choose a valid start and end date.");
  }
  if (from > to)
    throw new Error("The end date must be on or after the start date.");
  return { kind: "custom", start: from.toISOString(), end: to.toISOString() };
}

export function localInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function randomUsage(): number {
  return Math.floor(Math.random() * 10001) / 100;
}

export function summarize(records: UsageRecord[]) {
  const ordered = [...records].sort(
    (a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp),
  );
  return {
    ordered,
    latest: ordered[0]?.usage ?? null,
    average: ordered.length
      ? ordered.reduce((sum, record) => sum + record.usage, 0) / ordered.length
      : null,
    peak: ordered.length
      ? ordered.reduce((max, record) => Math.max(max, record.usage), -Infinity)
      : null,
    count: ordered.length,
  };
}
