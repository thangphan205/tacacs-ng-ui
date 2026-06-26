import { Button, Spinner, Text, VStack } from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { FiRefreshCw } from "react-icons/fi"
import { Tooltip } from "@/components/ui/tooltip"
import { fetchWithAuth, type HaInfo, type PushResult } from "@/haApi"
import useCustomToast from "@/hooks/useCustomToast"

export function SyncToStandby() {
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()

  const { data: haInfo, isLoading } = useQuery<HaInfo>({
    queryKey: ["ha-info"],
    queryFn: () => fetchWithAuth<HaInfo>("/api/v1/sync/ha-info"),
    staleTime: 30_000,
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: () =>
      fetchWithAuth<PushResult>("/api/v1/sync/push-config", { method: "POST" }),
    onSuccess: (data) => {
      const ok = data.results.filter((r) => r.status === "ok")
      const fail = data.results.filter((r) => r.status !== "ok")
      if (fail.length === 0) {
        showSuccessToast(
          `Config pushed to ${ok.length} node${ok.length !== 1 ? "s" : ""} successfully.`,
        )
      } else {
        showErrorToast(
          `${ok.length} ok, ${fail.length} failed: ${fail.map((r) => r.peer).join(", ")}`,
        )
      }
      queryClient.invalidateQueries({ queryKey: ["ha-info"] })
    },
    onError: (err: Error) => {
      showErrorToast(err.message)
    },
  })

  if (isLoading) return <Spinner size="sm" />

  if (haInfo?.node_role !== "primary" || haInfo.sync_mode !== "manual") {
    return null
  }

  const enabledPeers = (haInfo.peers ?? []).filter((p) => p.enabled)
  const reachablePeers = enabledPeers.filter((p) => p.available)
  const unreachablePeers = enabledPeers.filter((p) => p.available === false)
  const allUnreachable =
    enabledPeers.length > 0 && reachablePeers.length === 0

  const label =
    enabledPeers.length === 1
      ? "Sync to Standby"
      : `Sync to ${enabledPeers.length} Standbys`

  const tooltipContent = allUnreachable ? (
    <VStack align="start" gap={1}>
      <Text fontWeight="semibold">All peers unreachable:</Text>
      {unreachablePeers.map((p) => (
        <Text key={p.id} fontSize="xs">
          {p.name} ({p.url})
        </Text>
      ))}
    </VStack>
  ) : unreachablePeers.length > 0 ? (
    <VStack align="start" gap={1}>
      <Text fontWeight="semibold">
        {unreachablePeers.length} peer
        {unreachablePeers.length !== 1 ? "s" : ""} unreachable:
      </Text>
      {unreachablePeers.map((p) => (
        <Text key={p.id} fontSize="xs">
          {p.name}
        </Text>
      ))}
    </VStack>
  ) : (
    `Push active config to ${enabledPeers.length} standby node${enabledPeers.length !== 1 ? "s" : ""}`
  )

  return (
    <Tooltip content={tooltipContent}>
      <Button
        size="sm"
        colorPalette={allUnreachable ? "orange" : "blue"}
        variant="outline"
        onClick={() => mutation.mutate()}
        loading={mutation.isPending}
        disabled={mutation.isPending || enabledPeers.length === 0}
      >
        <FiRefreshCw />
        {label}
      </Button>
    </Tooltip>
  )
}
