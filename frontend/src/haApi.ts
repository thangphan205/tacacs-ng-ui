import { OpenAPI } from "@/client"

export interface HaInfo {
  node_role: "primary" | "standby"
  sync_mode: "auto" | "manual"
  scheduler_enabled: boolean
  peer_backend_url: string | null
  peer_available: boolean | null
  last_sync_at: string | null
}

export interface PromoteResult {
  status: string
  replication_lag_seconds: number | null
  next_steps: string[]
}

export async function fetchWithAuth<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const token = await (typeof OpenAPI.TOKEN === "function"
    ? OpenAPI.TOKEN({} as never)
    : Promise.resolve(OpenAPI.TOKEN ?? ""))
  const res = await fetch(`${OpenAPI.BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}
