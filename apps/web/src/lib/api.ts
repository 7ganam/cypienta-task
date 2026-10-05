import {
  historyPath,
  type TimeFilter,
  type UsageRecord,
  type UserInfo,
} from "./usage";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
    ...init,
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(payload?.error || `Request failed (${response.status}).`);
  if (payload === null)
    throw new Error("The backend returned an invalid response.");
  return payload as T;
}

export const getUser = (signal?: AbortSignal) =>
  request<UserInfo>("/api/user/info", { signal });
export const getUsage = (filter: TimeFilter, signal?: AbortSignal) =>
  request<UsageRecord[]>(historyPath(filter), { signal });

export async function createUsage(usage: number): Promise<UsageRecord> {
  const { csrfToken } = await request<{ csrfToken: string }>("/api/csrf");
  return request<UsageRecord>("/api/user/actions", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
    body: JSON.stringify({ usage }),
  });
}
