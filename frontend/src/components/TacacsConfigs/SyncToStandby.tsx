import { Button, Spinner } from "@chakra-ui/react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { FiRefreshCw } from "react-icons/fi"
import { Tooltip } from "@/components/ui/tooltip"
import { fetchWithAuth, type HaInfo } from "@/haApi"
import useCustomToast from "@/hooks/useCustomToast"

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
      fetchWithAuth<{ status: string; peer: string }>(
        "/api/v1/sync/push-config",
        {
          method: "POST",
        },
      ),
    onSuccess: (data) => {
      showSuccessToast(`Config pushed to ${data.peer} successfully.`)
    },
    onError: (err: Error) => {
      showErrorToast(err.message)
    },
  })

  if (isLoading) return <Spinner size="sm" />

  // Show button only on primary node with manual sync mode
  if (haInfo?.node_role !== "primary" || haInfo.sync_mode !== "manual") {
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
