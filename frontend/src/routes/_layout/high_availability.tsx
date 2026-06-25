import {
  Alert,
  Badge,
  Box,
  Container,
  EmptyState,
  Flex,
  Grid,
  Heading,
  Icon,
  Spinner,
  Stat,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  FiCheckCircle,
  FiGitMerge,
  FiInfo,
  FiServer,
  FiSettings,
  FiWifi,
  FiWifiOff,
  FiXCircle,
} from "react-icons/fi"
import { type HaInfo, fetchWithAuth } from "@/haApi"
import { SyncToStandby } from "@/components/TacacsConfigs/SyncToStandby"
import { Tooltip } from "@/components/ui/tooltip"

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

interface StatCardProps {
  label: string
  colorPalette: string
  icon: React.ElementType
  children: React.ReactNode
}

function StatCard({ label, colorPalette, icon: IconComp, children }: StatCardProps) {
  return (
    <Box
      p={5}
      bg="bg.panel"
      borderWidth="1px"
      borderLeftWidth="4px"
      borderLeftColor={`${colorPalette}.500`}
      borderRadius="xl"
      shadow="sm"
      transition="all 0.2s"
      _hover={{ shadow: "md" }}
    >
      <Flex align="center" justify="space-between">
        <Stat.Root>
          <Stat.Label
            fontSize="xs"
            fontWeight="semibold"
            textTransform="uppercase"
            letterSpacing="wider"
            color="fg.muted"
          >
            {label}
          </Stat.Label>
          <Box mt={2}>{children}</Box>
        </Stat.Root>
        <Box
          p={3}
          bg={`${colorPalette}.muted`}
          color={`${colorPalette}.fg`}
          borderRadius="lg"
          shadow="xs"
        >
          <IconComp fontSize="22px" />
        </Box>
      </Flex>
    </Box>
  )
}

function HighAvailabilityPage() {
  const { data: haInfo, isLoading } = useQuery<HaInfo>({
    queryKey: ["ha-info"],
    queryFn: () => fetchWithAuth<HaInfo>("/api/v1/sync/ha-info"),
    refetchInterval: 30_000,
    staleTime: 30_000,
    retry: false,
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

  const haConfigured = !!haInfo?.peer_backend_url

  return (
    <Container maxW="4xl" py={6}>
      <Flex align="center" gap={3} mb={6}>
        <Icon as={FiGitMerge} fontSize="2xl" color="teal.500" />
        <Heading size="lg">High Availability</Heading>
        {haInfo && (
          <Badge
            colorPalette={haInfo.node_role === "primary" ? "blue" : "purple"}
            variant="subtle"
            size="md"
            ml={1}
          >
            {haInfo.node_role === "primary" ? "Primary" : "Standby"}
          </Badge>
        )}
      </Flex>

      {!haConfigured ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiGitMerge />
            </EmptyState.Indicator>
            <EmptyState.Title>High Availability not configured</EmptyState.Title>
            <EmptyState.Description>
              Set <Text as="code">PEER_BACKEND_URL</Text> and{" "}
              <Text as="code">INTERNAL_SYNC_TOKEN</Text> in the environment to
              enable HA sync.
            </EmptyState.Description>
          </EmptyState.Content>
        </EmptyState.Root>
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
            {/* Node Role */}
            <StatCard
              label="Node Role"
              colorPalette={haInfo?.node_role === "primary" ? "blue" : "purple"}
              icon={FiServer}
            >
              <Text fontSize="2xl" fontWeight="extrabold" fontFamily="mono">
                {haInfo?.node_role === "primary" ? "Primary" : "Standby"}
              </Text>
            </StatCard>

            {/* Peer Status */}
            <StatCard
              label="Peer Status"
              colorPalette={
                haInfo?.peer_available === true
                  ? "green"
                  : haInfo?.peer_available === false
                    ? "red"
                    : "gray"
              }
              icon={
                haInfo?.peer_available === true
                  ? FiWifi
                  : haInfo?.peer_available === false
                    ? FiWifiOff
                    : FiInfo
              }
            >
              <Flex align="center" gap={2} mt={1}>
                <Icon
                  as={
                    haInfo?.peer_available === true
                      ? FiCheckCircle
                      : haInfo?.peer_available === false
                        ? FiXCircle
                        : FiInfo
                  }
                  color={
                    haInfo?.peer_available === true
                      ? "green.500"
                      : haInfo?.peer_available === false
                        ? "red.500"
                        : "gray.400"
                  }
                  fontSize="xl"
                />
                <Text fontSize="xl" fontWeight="bold" fontFamily="mono">
                  {haInfo?.peer_available === true
                    ? "Connected"
                    : haInfo?.peer_available === false
                      ? "Unreachable"
                      : "Checking…"}
                </Text>
              </Flex>
            </StatCard>

            {/* Sync Mode */}
            <StatCard
              label="Sync Mode"
              colorPalette={haInfo?.sync_mode === "auto" ? "teal" : "orange"}
              icon={FiSettings}
            >
              <Text fontSize="2xl" fontWeight="extrabold" fontFamily="mono" textTransform="capitalize">
                {haInfo?.sync_mode ?? "—"}
              </Text>
            </StatCard>
          </Grid>

          {/* Detail panel */}
          <Box
            p={5}
            bg="bg.panel"
            borderWidth="1px"
            borderRadius="xl"
            shadow="sm"
          >
            <Heading size="sm" mb={4} color="fg.muted">
              Details
            </Heading>
            <VStack align="stretch" gap={3}>
              <Flex justify="space-between" align="center">
                <Text fontSize="sm" color="fg.muted">
                  Peer URL
                </Text>
                <Text fontSize="sm" fontFamily="mono" fontWeight="medium">
                  {haInfo?.peer_backend_url ?? "—"}
                </Text>
              </Flex>

              <Flex justify="space-between" align="center">
                <Text fontSize="sm" color="fg.muted">
                  Last sync
                </Text>
                {haInfo?.last_sync_at ? (
                  <Tooltip content={formatAbsoluteTime(haInfo.last_sync_at)}>
                    <Text
                      fontSize="sm"
                      fontWeight="medium"
                      cursor="default"
                      borderBottomWidth="1px"
                      borderBottomStyle="dashed"
                      borderBottomColor="border.muted"
                    >
                      {formatRelativeTime(haInfo.last_sync_at)}
                    </Text>
                  </Tooltip>
                ) : (
                  <Text fontSize="sm" color="fg.subtle">
                    —
                  </Text>
                )}
              </Flex>

              <Flex justify="space-between" align="center">
                <Text fontSize="sm" color="fg.muted">
                  Scheduler
                </Text>
                <Badge
                  colorPalette={haInfo?.scheduler_enabled ? "green" : "gray"}
                  variant="subtle"
                  size="sm"
                >
                  {haInfo?.scheduler_enabled ? "Enabled" : "Disabled"}
                </Badge>
              </Flex>
            </VStack>
          </Box>

          {/* Manual sync action */}
          {haInfo?.node_role === "primary" && haInfo.sync_mode === "manual" && (
            <Flex justify="flex-end">
              <SyncToStandby />
            </Flex>
          )}
        </VStack>
      )}
    </Container>
  )
}
