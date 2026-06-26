import {
  Alert,
  Badge,
  Box,
  Button,
  Container,
  EmptyState,
  Flex,
  Grid,
  Heading,
  Icon,
  IconButton,
  Input,
  List,
  Spinner,
  Switch,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import React from "react"
import {
  FiAlertTriangle,
  FiCheckCircle,
  FiGitMerge,
  FiInfo,
  FiPlus,
  FiServer,
  FiSettings,
  FiTrash2,
  FiWifi,
  FiWifiOff,
  FiXCircle,
  FiZap,
} from "react-icons/fi"
import { SyncToStandby } from "@/components/TacacsConfigs/SyncToStandby"
import { Tooltip } from "@/components/ui/tooltip"
import {
  fetchWithAuth,
  type HaConfigUpdate,
  type HaInfo,
  type HaPeer,
  type HaPeerCreate,
  type PromoteResult,
} from "@/haApi"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/high_availability")({
  component: HighAvailabilityPage,
})

function formatRelativeTime(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffMs = now - then
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  return `${Math.floor(diffHr / 24)}d ago`
}

function formatAbsoluteTime(isoString: string): string {
  return new Date(isoString).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  })
}

function PeerAvailableBadge({ peer }: { peer: HaPeer }) {
  if (!peer.enabled)
    return (
      <Badge colorPalette="gray" variant="subtle" size="sm">
        Disabled
      </Badge>
    )
  if (peer.available === true)
    return (
      <Badge colorPalette="green" variant="subtle" size="sm">
        <Icon as={FiCheckCircle} mr={1} />
        Online
      </Badge>
    )
  if (peer.available === false)
    return (
      <Badge colorPalette="red" variant="subtle" size="sm">
        <Icon as={FiXCircle} mr={1} />
        Unreachable
      </Badge>
    )
  return (
    <Badge colorPalette="gray" variant="subtle" size="sm">
      <Icon as={FiInfo} mr={1} />
      Checking…
    </Badge>
  )
}

interface AddPeerRowProps {
  onAdd: (peer: HaPeerCreate) => void
  isPending: boolean
}

function AddPeerRow({ onAdd, isPending }: AddPeerRowProps) {
  const [name, setName] = React.useState("")
  const [url, setUrl] = React.useState("")

  function submit() {
    if (!name.trim() || !url.trim()) return
    onAdd({ name: name.trim(), url: url.trim(), enabled: true })
    setName("")
    setUrl("")
  }

  return (
    <Table.Row>
      <Table.Cell>
        <Input
          size="sm"
          placeholder="Zone B"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </Table.Cell>
      <Table.Cell>
        <Input
          size="sm"
          placeholder="http://standby:8000"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
      </Table.Cell>
      <Table.Cell />
      <Table.Cell />
      <Table.Cell>
        <Button
          size="sm"
          colorPalette="blue"
          onClick={submit}
          loading={isPending}
          disabled={!name.trim() || !url.trim()}
        >
          <FiPlus />
          Add
        </Button>
      </Table.Cell>
    </Table.Row>
  )
}

interface PeersTableProps {
  peers: HaPeer[]
  isSuperuser: boolean
  onToggle: (peer: HaPeer) => void
  onDelete: (peer: HaPeer) => void
  onAdd: (peer: HaPeerCreate) => void
  addPending: boolean
  mutatePending: boolean
}

function PeersTable({
  peers,
  isSuperuser,
  onToggle,
  onDelete,
  onAdd,
  addPending,
  mutatePending,
}: PeersTableProps) {
  return (
    <Box
      bg="bg.panel"
      borderWidth="1px"
      borderRadius="xl"
      shadow="sm"
      overflow="hidden"
    >
      <Flex px={5} py={4} align="center" justify="space-between">
        <Heading size="sm" color="fg.muted">
          Standby Peers
        </Heading>
        <Badge colorPalette="blue" variant="subtle">
          {peers.length} node{peers.length !== 1 ? "s" : ""}
        </Badge>
      </Flex>
      <Table.Root size="sm">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader>Name</Table.ColumnHeader>
            <Table.ColumnHeader>URL</Table.ColumnHeader>
            <Table.ColumnHeader>Status</Table.ColumnHeader>
            <Table.ColumnHeader>Last Sync</Table.ColumnHeader>
            {isSuperuser && <Table.ColumnHeader />}
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {peers.map((peer) => (
            <Table.Row key={peer.id}>
              <Table.Cell fontWeight="medium">{peer.name}</Table.Cell>
              <Table.Cell fontFamily="mono" fontSize="xs" color="fg.muted">
                {peer.url}
              </Table.Cell>
              <Table.Cell>
                <PeerAvailableBadge peer={peer} />
              </Table.Cell>
              <Table.Cell fontSize="xs" color="fg.muted">
                {peer.last_push_at ? (
                  <Tooltip content={formatAbsoluteTime(peer.last_push_at)}>
                    <Text
                      cursor="default"
                      borderBottomWidth="1px"
                      borderBottomStyle="dashed"
                      borderBottomColor="border.muted"
                    >
                      {formatRelativeTime(peer.last_push_at)}
                    </Text>
                  </Tooltip>
                ) : (
                  "—"
                )}
              </Table.Cell>
              {isSuperuser && (
                <Table.Cell>
                  <Flex gap={2} justify="flex-end">
                    <Tooltip
                      content={peer.enabled ? "Disable peer" : "Enable peer"}
                    >
                      <Switch.Root
                        size="sm"
                        checked={peer.enabled}
                        onCheckedChange={() => onToggle(peer)}
                        disabled={mutatePending}
                      >
                        <Switch.HiddenInput />
                        <Switch.Control />
                      </Switch.Root>
                    </Tooltip>
                    <Tooltip content="Remove peer">
                      <IconButton
                        size="xs"
                        variant="ghost"
                        colorPalette="red"
                        aria-label="Delete peer"
                        onClick={() => onDelete(peer)}
                        disabled={mutatePending}
                      >
                        <FiTrash2 />
                      </IconButton>
                    </Tooltip>
                  </Flex>
                </Table.Cell>
              )}
            </Table.Row>
          ))}
          {isSuperuser && <AddPeerRow onAdd={onAdd} isPending={addPending} />}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}

interface HaSettingsFormProps {
  haInfo: HaInfo
}

function HaSettingsForm({ haInfo }: HaSettingsFormProps) {
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const [nodeName, setNodeName] = React.useState(haInfo.node_name)
  const [syncMode, setSyncMode] = React.useState(haInfo.sync_mode)
  const [schedulerEnabled, setSchedulerEnabled] = React.useState(
    haInfo.scheduler_enabled,
  )
  const [statsInterval, setStatsInterval] = React.useState(
    String(haInfo.stats_interval_minutes),
  )

  const mutation = useMutation({
    mutationFn: (body: HaConfigUpdate) =>
      fetchWithAuth("/api/v1/sync/config", {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      showSuccessToast("HA settings updated.")
      queryClient.invalidateQueries({ queryKey: ["ha-info"] })
    },
    onError: (err: Error) => showErrorToast(err.message),
  })

  function save() {
    mutation.mutate({
      node_name: nodeName,
      sync_mode: syncMode,
      scheduler_enabled: schedulerEnabled,
      stats_interval_minutes: parseInt(statsInterval, 10) || 0,
    })
  }

  return (
    <Box p={5} bg="bg.panel" borderWidth="1px" borderRadius="xl" shadow="sm">
      <Heading size="sm" mb={4} color="fg.muted">
        HA Settings
      </Heading>
      <VStack align="stretch" gap={3}>
        <Flex justify="space-between" align="center">
          <Text fontSize="sm" color="fg.muted">
            Node name
          </Text>
          <Input
            size="sm"
            w="40"
            value={nodeName}
            onChange={(e) => setNodeName(e.target.value)}
          />
        </Flex>
        <Flex justify="space-between" align="center">
          <Text fontSize="sm" color="fg.muted">
            Sync mode
          </Text>
          <Flex gap={2}>
            {(["auto", "manual"] as const).map((m) => (
              <Button
                key={m}
                size="xs"
                variant={syncMode === m ? "solid" : "outline"}
                colorPalette="teal"
                onClick={() => setSyncMode(m)}
                textTransform="capitalize"
              >
                {m}
              </Button>
            ))}
          </Flex>
        </Flex>
        <Flex justify="space-between" align="center">
          <Text fontSize="sm" color="fg.muted">
            Scheduler enabled
          </Text>
          <Switch.Root
            size="sm"
            checked={schedulerEnabled}
            onCheckedChange={(e) => setSchedulerEnabled(e.checked)}
          >
            <Switch.HiddenInput />
            <Switch.Control />
          </Switch.Root>
        </Flex>
        <Flex justify="space-between" align="center">
          <Text fontSize="sm" color="fg.muted">
            Stats interval (min)
          </Text>
          <Input
            size="sm"
            w="20"
            type="number"
            min={0}
            value={statsInterval}
            onChange={(e) => setStatsInterval(e.target.value)}
          />
        </Flex>
        <Flex justify="flex-end">
          <Button
            size="sm"
            colorPalette="blue"
            onClick={save}
            loading={mutation.isPending}
          >
            Save
          </Button>
        </Flex>
      </VStack>
    </Box>
  )
}

function HighAvailabilityPage() {
  const { user } = useAuth()
  const isSuperuser = user?.is_superuser ?? false
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()

  const { data: haInfo, isLoading } = useQuery<HaInfo>({
    queryKey: ["ha-info"],
    queryFn: () => fetchWithAuth<HaInfo>("/api/v1/sync/ha-info"),
    refetchInterval: 30_000,
    staleTime: 30_000,
    retry: false,
  })

  const [promoteResult, setPromoteResult] =
    React.useState<PromoteResult | null>(null)
  const [confirmPromote, setConfirmPromote] = React.useState(false)

  const promoteMutation = useMutation({
    mutationFn: () =>
      fetchWithAuth<PromoteResult>("/api/v1/sync/promote", { method: "POST" }),
    onSuccess: (data) => {
      setPromoteResult(data)
      setConfirmPromote(false)
    },
  })

  const addPeerMutation = useMutation({
    mutationFn: (body: HaPeerCreate) =>
      fetchWithAuth("/api/v1/sync/peers", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      showSuccessToast("Peer added.")
      queryClient.invalidateQueries({ queryKey: ["ha-info"] })
    },
    onError: (err: Error) => showErrorToast(err.message),
  })

  const updatePeerMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<HaPeer> }) =>
      fetchWithAuth(`/api/v1/sync/peers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ha-info"] })
    },
    onError: (err: Error) => showErrorToast(err.message),
  })

  const deletePeerMutation = useMutation({
    mutationFn: (id: string) =>
      fetchWithAuth(`/api/v1/sync/peers/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      showSuccessToast("Peer removed.")
      queryClient.invalidateQueries({ queryKey: ["ha-info"] })
    },
    onError: (err: Error) => showErrorToast(err.message),
  })

  if (isLoading) {
    return (
      <Container maxW="4xl" py={8}>
        <Flex justify="center" align="center" h="40">
          <Spinner size="lg" />
        </Flex>
      </Container>
    )
  }

  const haConfigured =
    haInfo?.node_role === "standby" ||
    (haInfo?.peers?.length ?? 0) > 0 ||
    !!haInfo?.peer_backend_url

  return (
    <Container maxW="4xl" py={6}>
      <Flex align="center" gap={3} mb={6}>
        <Icon as={FiGitMerge} fontSize="2xl" color="teal.500" />
        <Heading size="lg">High Availability</Heading>
        {haInfo && (
          <>
            <Badge
              colorPalette={haInfo.node_role === "primary" ? "blue" : "purple"}
              variant="subtle"
              size="md"
              ml={1}
            >
              {haInfo.node_role === "primary" ? "Primary" : "Standby"}
            </Badge>
            {haInfo.node_name && (
              <Badge colorPalette="gray" variant="outline" size="md">
                {haInfo.node_name}
              </Badge>
            )}
          </>
        )}
      </Flex>

      {!haConfigured ? (
        <VStack gap={6} align="stretch">
          <EmptyState.Root>
            <EmptyState.Content>
              <EmptyState.Indicator>
                <FiGitMerge />
              </EmptyState.Indicator>
              <EmptyState.Title>
                High Availability not configured
              </EmptyState.Title>
              <EmptyState.Description>
                Add a peer node below, or set{" "}
                <Text as="code">PEER_BACKEND_URL</Text> /{" "}
                <Text as="code">PEER_NODES</Text> in the environment.
              </EmptyState.Description>
            </EmptyState.Content>
          </EmptyState.Root>

          {haInfo && haInfo.node_role === "primary" && (
            <PeersTable
              peers={haInfo.peers}
              isSuperuser={isSuperuser}
              onToggle={(peer) =>
                updatePeerMutation.mutate({
                  id: peer.id,
                  body: { enabled: !peer.enabled },
                })
              }
              onDelete={(peer) => deletePeerMutation.mutate(peer.id)}
              onAdd={(peer) => addPeerMutation.mutate(peer)}
              addPending={addPeerMutation.isPending}
              mutatePending={
                updatePeerMutation.isPending || deletePeerMutation.isPending
              }
            />
          )}
        </VStack>
      ) : (
        <VStack gap={6} align="stretch">
          {/* Standby read-only notice */}
          {haInfo?.node_role === "standby" && (
            <Alert.Root status="info" borderRadius="xl">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title>Read-only mode</Alert.Title>
                <Alert.Description>
                  This node is in standby mode. Make configuration changes on
                  the primary node.
                </Alert.Description>
              </Alert.Content>
            </Alert.Root>
          )}

          {/* Stat cards */}
          <Grid templateColumns="repeat(3, 1fr)" gap={4}>
            <Box
              p={5}
              bg="bg.panel"
              borderWidth="1px"
              borderLeftWidth="4px"
              borderLeftColor={
                haInfo?.node_role === "primary" ? "blue.500" : "purple.500"
              }
              borderRadius="xl"
              shadow="sm"
            >
              <Flex align="center" justify="space-between">
                <Box>
                  <Text
                    fontSize="xs"
                    fontWeight="semibold"
                    textTransform="uppercase"
                    letterSpacing="wider"
                    color="fg.muted"
                  >
                    Node Role
                  </Text>
                  <Text
                    fontSize="2xl"
                    fontWeight="extrabold"
                    fontFamily="mono"
                    mt={2}
                  >
                    {haInfo?.node_role === "primary" ? "Primary" : "Standby"}
                  </Text>
                </Box>
                <Box
                  p={3}
                  bg={
                    haInfo?.node_role === "primary"
                      ? "blue.muted"
                      : "purple.muted"
                  }
                  color={
                    haInfo?.node_role === "primary" ? "blue.fg" : "purple.fg"
                  }
                  borderRadius="lg"
                >
                  <FiServer fontSize="22px" />
                </Box>
              </Flex>
            </Box>

            {haInfo?.node_role === "primary" ? (
              <Box
                p={5}
                bg="bg.panel"
                borderWidth="1px"
                borderLeftWidth="4px"
                borderLeftColor={
                  (haInfo?.peers ?? []).some((p) => p.available)
                    ? "green.500"
                    : "red.500"
                }
                borderRadius="xl"
                shadow="sm"
              >
                <Flex align="center" justify="space-between">
                  <Box>
                    <Text
                      fontSize="xs"
                      fontWeight="semibold"
                      textTransform="uppercase"
                      letterSpacing="wider"
                      color="fg.muted"
                    >
                      Peers Online
                    </Text>
                    <Text
                      fontSize="2xl"
                      fontWeight="extrabold"
                      fontFamily="mono"
                      mt={2}
                    >
                      {(haInfo?.peers ?? []).filter((p) => p.available).length}{" "}
                      / {(haInfo?.peers ?? []).filter((p) => p.enabled).length}
                    </Text>
                  </Box>
                  <Box
                    p={3}
                    bg={
                      (haInfo?.peers ?? []).some((p) => p.available)
                        ? "green.muted"
                        : "red.muted"
                    }
                    color={
                      (haInfo?.peers ?? []).some((p) => p.available)
                        ? "green.fg"
                        : "red.fg"
                    }
                    borderRadius="lg"
                  >
                    {(haInfo?.peers ?? []).some((p) => p.available) ? (
                      <FiWifi fontSize="22px" />
                    ) : (
                      <FiWifiOff fontSize="22px" />
                    )}
                  </Box>
                </Flex>
              </Box>
            ) : (
              <Box
                p={5}
                bg="bg.panel"
                borderWidth="1px"
                borderLeftWidth="4px"
                borderLeftColor={
                  haInfo?.last_sync_at ? "green.500" : "gray.400"
                }
                borderRadius="xl"
                shadow="sm"
              >
                <Flex align="center" justify="space-between">
                  <Box>
                    <Text
                      fontSize="xs"
                      fontWeight="semibold"
                      textTransform="uppercase"
                      letterSpacing="wider"
                      color="fg.muted"
                    >
                      Last Sync Received
                    </Text>
                    <Text
                      fontSize="xl"
                      fontWeight="extrabold"
                      fontFamily="mono"
                      mt={2}
                    >
                      {haInfo?.last_sync_at
                        ? formatRelativeTime(haInfo.last_sync_at)
                        : "Never"}
                    </Text>
                  </Box>
                  <Box
                    p={3}
                    bg={haInfo?.last_sync_at ? "green.muted" : "gray.muted"}
                    color={haInfo?.last_sync_at ? "green.fg" : "gray.fg"}
                    borderRadius="lg"
                  >
                    <FiWifi fontSize="22px" />
                  </Box>
                </Flex>
              </Box>
            )}

            <Box
              p={5}
              bg="bg.panel"
              borderWidth="1px"
              borderLeftWidth="4px"
              borderLeftColor={
                haInfo?.sync_mode === "auto" ? "teal.500" : "orange.500"
              }
              borderRadius="xl"
              shadow="sm"
            >
              <Flex align="center" justify="space-between">
                <Box>
                  <Text
                    fontSize="xs"
                    fontWeight="semibold"
                    textTransform="uppercase"
                    letterSpacing="wider"
                    color="fg.muted"
                  >
                    Sync Mode
                  </Text>
                  <Text
                    fontSize="2xl"
                    fontWeight="extrabold"
                    fontFamily="mono"
                    textTransform="capitalize"
                    mt={2}
                  >
                    {haInfo?.sync_mode ?? "—"}
                  </Text>
                </Box>
                <Box
                  p={3}
                  bg={
                    haInfo?.sync_mode === "auto" ? "teal.muted" : "orange.muted"
                  }
                  color={haInfo?.sync_mode === "auto" ? "teal.fg" : "orange.fg"}
                  borderRadius="lg"
                >
                  <FiSettings fontSize="22px" />
                </Box>
              </Flex>
            </Box>
          </Grid>

          {/* Peers table — primary only */}
          {haInfo && haInfo.node_role === "primary" && (
            <PeersTable
              peers={haInfo.peers}
              isSuperuser={isSuperuser}
              onToggle={(peer) =>
                updatePeerMutation.mutate({
                  id: peer.id,
                  body: { enabled: !peer.enabled },
                })
              }
              onDelete={(peer) => deletePeerMutation.mutate(peer.id)}
              onAdd={(peer) => addPeerMutation.mutate(peer)}
              addPending={addPeerMutation.isPending}
              mutatePending={
                updatePeerMutation.isPending || deletePeerMutation.isPending
              }
            />
          )}

          {/* Primary URL info — standby only */}
          {haInfo?.node_role === "standby" && haInfo.peer_backend_url && (
            <Box
              p={4}
              bg="bg.panel"
              borderWidth="1px"
              borderRadius="xl"
              shadow="sm"
            >
              <Text
                fontSize="xs"
                fontWeight="semibold"
                textTransform="uppercase"
                letterSpacing="wider"
                color="fg.muted"
                mb={1}
              >
                Primary Node
              </Text>
              <Text fontFamily="mono" fontSize="sm">
                {haInfo.peer_backend_url}
              </Text>
            </Box>
          )}

          {/* Last sync */}
          {haInfo?.last_sync_at && (
            <Flex justify="flex-end">
              <Text fontSize="xs" color="fg.subtle">
                Last sync:{" "}
                <Tooltip content={formatAbsoluteTime(haInfo.last_sync_at)}>
                  <Text
                    as="span"
                    fontWeight="medium"
                    cursor="default"
                    borderBottomWidth="1px"
                    borderBottomStyle="dashed"
                    borderBottomColor="border.muted"
                  >
                    {formatRelativeTime(haInfo.last_sync_at)}
                  </Text>
                </Tooltip>
              </Text>
            </Flex>
          )}

          {/* HA Settings (primary + superuser) */}
          {haInfo && haInfo.node_role === "primary" && isSuperuser && (
            <HaSettingsForm haInfo={haInfo} />
          )}

          {/* Manual sync action */}
          {haInfo?.node_role === "primary" && haInfo.sync_mode === "manual" && (
            <Flex justify="flex-end">
              <SyncToStandby />
            </Flex>
          )}

          {/* Promote to Primary — standby + superuser only */}
          {haInfo?.node_role === "standby" && isSuperuser && (
            <Box
              p={5}
              bg="bg.panel"
              borderWidth="1px"
              borderLeftWidth="4px"
              borderLeftColor="red.500"
              borderRadius="xl"
              shadow="sm"
            >
              <Heading size="sm" mb={2} color="red.500">
                Failover — Promote to Primary
              </Heading>
              <Text fontSize="sm" color="fg.muted" mb={4}>
                Run <Text as="code">pg_promote()</Text> on this node's database
                to make it accept writes. After promotion, update{" "}
                <Text as="code">.env</Text> and restart the backend.
              </Text>

              {promoteResult ? (
                <VStack align="stretch" gap={3}>
                  <Alert.Root status="success" borderRadius="lg">
                    <Alert.Indicator />
                    <Alert.Content>
                      <Alert.Title>Promoted successfully</Alert.Title>
                      {promoteResult.replication_lag_seconds !== null && (
                        <Alert.Description>
                          Replication lag at promotion:{" "}
                          {promoteResult.replication_lag_seconds}s
                        </Alert.Description>
                      )}
                    </Alert.Content>
                  </Alert.Root>
                  <Alert.Root status="warning" borderRadius="lg">
                    <Alert.Indicator>
                      <FiAlertTriangle />
                    </Alert.Indicator>
                    <Alert.Content>
                      <Alert.Title>Review the Peers table</Alert.Title>
                      <Alert.Description>
                        The old primary's URL has been added as a peer
                        automatically. Disable or remove it until Zone A
                        recovers, then verify remaining standbys are replicating
                        from this node.
                      </Alert.Description>
                    </Alert.Content>
                  </Alert.Root>
                  <Box>
                    <Text fontSize="sm" fontWeight="semibold" mb={2}>
                      Complete these steps to finish failover:
                    </Text>
                    <List.Root gap={1}>
                      {promoteResult.next_steps.map((step) => (
                        <List.Item key={step} fontSize="sm" fontFamily="mono">
                          {step}
                        </List.Item>
                      ))}
                    </List.Root>
                  </Box>
                </VStack>
              ) : confirmPromote ? (
                <VStack align="stretch" gap={3}>
                  <Alert.Root status="warning" borderRadius="lg">
                    <Alert.Indicator>
                      <FiAlertTriangle />
                    </Alert.Indicator>
                    <Alert.Content>
                      <Alert.Title>Confirm promotion</Alert.Title>
                      <Alert.Description>
                        This will break replication from the old primary.
                        Proceed only if Zone A is down.
                      </Alert.Description>
                    </Alert.Content>
                  </Alert.Root>
                  <Flex gap={3}>
                    <Button
                      colorPalette="red"
                      size="sm"
                      onClick={() => promoteMutation.mutate()}
                      loading={promoteMutation.isPending}
                    >
                      <FiZap />
                      Confirm — Promote Now
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setConfirmPromote(false)}
                      disabled={promoteMutation.isPending}
                    >
                      Cancel
                    </Button>
                  </Flex>
                  {promoteMutation.isError && (
                    <Text fontSize="sm" color="red.500">
                      {(promoteMutation.error as Error).message}
                    </Text>
                  )}
                </VStack>
              ) : (
                <Button
                  colorPalette="red"
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirmPromote(true)}
                >
                  <FiZap />
                  Promote to Primary
                </Button>
              )}
            </Box>
          )}
        </VStack>
      )}
    </Container>
  )
}
