import { Button, Spinner } from "@chakra-ui/react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { FiRefreshCw } from "react-icons/fi"
import { OpenAPI } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { Tooltip } from "@/components/ui/tooltip"

interface HaInfo {
  node_role: "primary" | "standby"
  sync_mode: "auto" | "manual"
  scheduler_enabled: boolean
  peer_backend_url: string | null
  peer_available: boolean | null
}

async function fetchWithAuth<T>(path: string, options?: RequestInit): Promise<T> {
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

export function SyncToStandby() {
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: haInfo, isLoading } = useQuery<HaInfo>({
    queryKey: ["ha-info"],
    queryFn: () => fetchWithAuth<HaInfo>("/api/v1/sync/ha-info"),
    staleTime: 30_000,
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: () =>
      fetchWithAuth<{ status: string; peer: string }>("/api/v1/sync/push-config", {
        method: "POST",
      }),
    onSuccess: (data) => {
      showSuccessToast(`Config pushed to ${data.peer} successfully.`)
    },
    onError: (err: Error) => {
      showErrorToast(err.message)
    },
  })

  if (isLoading) return <Spinner size="sm" />

  // Show button only on primary node with manual sync mode
  if (!haInfo || haInfo.node_role !== "primary" || haInfo.sync_mode !== "manual") {
    return null
  }

  const peerOk = haInfo.peer_available === true

  return (
    <Tooltip
      content={
        peerOk
          ? "Push active config to standby node"
          : "Standby node is unreachable — config will not be applied"
      }
    >
      <Button
        size="sm"
        colorPalette={peerOk ? "blue" : "orange"}
        variant="outline"
        onClick={() => mutation.mutate()}
        loading={mutation.isPending}
        disabled={mutation.isPending}
      >
        <FiRefreshCw />
        Sync to Zone B
      </Button>
    </Tooltip>
  )
}
