import { OpenAPI } from "@/client"

export interface HaPeer {
  id: string
  name: string
  url: string
  enabled: boolean
  available: boolean | null
  last_push_at: string | null
}

export interface HaInfo {
  node_role: "primary" | "standby"
  node_name: string
  sync_mode: "auto" | "manual"
  scheduler_enabled: boolean
  stats_interval_minutes: number
  peers: HaPeer[]
  // backward-compat single-peer fields
  peer_backend_url: string | null
  peer_available: boolean | null
  last_sync_at: string | null
}

export interface HaConfigUpdate {
  node_name?: string
  sync_mode?: "auto" | "manual"
  scheduler_enabled?: boolean
  stats_interval_minutes?: number
}

export interface HaPeerCreate {
  name: string
  url: string
  enabled: boolean
}

export interface PushResult {
  results: Array<{ peer: string; url: string; status: "ok" | "error" }>
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
