import {
  Badge,
  Box,
  Container,
  EmptyState,
  Flex,
  Grid,
  HStack,
  Skeleton,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { type ReactNode, useState } from "react"
import {
  FiAlertCircle,
  FiAlertTriangle,
  FiBell,
  FiCheckCircle,
  FiChevronRight,
  FiClock,
  FiMinusCircle,
  FiXCircle,
} from "react-icons/fi"
import { z } from "zod"

import { type AlertEventPublic, AlertEventsService } from "@/client"
import {
  AlertEventDetails,
  SEVERITY_COLORS,
  STATUS_COLORS,
  STATUS_LABELS,
  summarizePayload,
} from "@/components/AlertEvents/AlertEventDetails"
import { FilterSelect } from "@/components/Common/FilterSelect"
import { ListToolbar } from "@/components/Common/ListToolbar"
import { PageHeader } from "@/components/Common/PageHeader"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { RefreshControl } from "@/components/Common/RefreshControl"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"
import { formatDateTime } from "@/utils"

const DEFAULT_PER_PAGE = 10

const searchSchema = z.object({
  page: z.number().catch(1),
  status: z.string().optional(),
})

const STATUS_OPTIONS = [
  { value: "sent", label: "Sent" },
  { value: "failed", label: "Failed" },
  { value: "no_channel", label: "No channel" },
]

const SEVERITY_ORDER = ["critical", "high", "medium", "low"]

function StatusIcon({ status }: { status?: string }) {
  if (status === "sent") return <FiCheckCircle size={11} />
  if (status === "failed") return <FiXCircle size={11} />
  return <FiMinusCircle size={11} />
}

function ChannelCell({ ev }: { ev: AlertEventPublic }) {
  if (ev.channel_name) {
    return (
      <Text fontSize="xs" truncate maxW="180px" title={ev.channel_name}>
        {ev.channel_name}
      </Text>
    )
  }
  return (
    <Text as="span" fontSize="xs" color="fg.muted" fontStyle="italic">
      {ev.status === "no_channel"
        ? "No channel configured"
        : ev.channel_id
          ? ev.channel_id
          : "Deleted channel"}
    </Text>
  )
}

interface QueryParams {
  page: number
  perPage: number
  status?: string
}

function getQueryOptions({ page, perPage, status }: QueryParams) {
  return {
    queryFn: () =>
      AlertEventsService.readAlertEvents({
        skip: (page - 1) * perPage,
        limit: perPage,
        status: status ?? undefined,
      }),
    queryKey: ["alert_events", { page, perPage, status }],
  }
}

export const Route = createFileRoute("/_layout/alert_events")({
  component: AlertEventsPage,
  validateSearch: (search) => searchSchema.parse(search),
})

interface KpiCardProps {
  label: string
  value: number
  icon: ReactNode
  colorPalette: string
  active?: boolean
  onClick?: () => void
}

function KpiCard({
  label,
  value,
  icon,
  colorPalette,
  active = false,
  onClick,
}: KpiCardProps) {
  return (
    <Box
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      textAlign="left"
      borderWidth="1px"
      borderColor={active ? `${colorPalette}.solid` : "border"}
      borderRadius="xl"
      p={4}
      bg="bg.panel"
      shadow="xs"
      cursor={onClick ? "pointer" : "default"}
      transition="border-color 0.15s, box-shadow 0.15s"
      _hover={
        onClick
          ? { borderColor: `${colorPalette}.solid`, shadow: "sm" }
          : undefined
      }
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault()
                onClick()
              }
            }
          : undefined
      }
    >
      <Flex align="center" justify="space-between" mb={2}>
        <Text fontSize="xs" fontWeight="medium" color="fg.muted">
          {label}
        </Text>
        <Box
          p={1.5}
          borderRadius="md"
          bg={`${colorPalette}.subtle`}
          color={`${colorPalette}.fg`}
        >
          {icon}
        </Box>
      </Flex>
      <Text
        fontSize="2xl"
        fontWeight="bold"
        lineHeight="1"
        fontVariantNumeric="tabular-nums"
      >
        {value.toLocaleString()}
      </Text>
    </Box>
  )
}

function AlertStatisticsPanel({
  activeStatus,
  onSelectStatus,
  refetchInterval,
}: {
  activeStatus?: string
  onSelectStatus: (status?: string) => void
  refetchInterval: number | false
}) {
  const { data, isLoading } = useQuery({
    queryFn: () => AlertEventsService.readAlertStatistics(),
    queryKey: ["alert_statistics"],
    refetchInterval,
  })

  if (isLoading) {
    return (
      <Grid
        templateColumns={{ base: "repeat(2, 1fr)", md: "repeat(5, 1fr)" }}
        gap={4}
        mb={6}
      >
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} h="88px" borderRadius="xl" />
        ))}
      </Grid>
    )
  }

  if (!data) return null

  const severityTotal =
    data.by_severity.reduce((acc, s) => acc + s.count, 0) || 1
  const maxRuleCount = Math.max(...data.by_rule.map((r) => r.count), 1)

  const toggleStatus = (target?: string) => {
    onSelectStatus(activeStatus === target ? undefined : target)
  }

  return (
    <Box mb={6}>
      <Grid
        templateColumns={{ base: "repeat(2, 1fr)", md: "repeat(5, 1fr)" }}
        gap={4}
        mb={4}
      >
        <KpiCard
          label="Total Alerts"
          value={data.total}
          icon={<FiBell size={14} />}
          colorPalette="teal"
          active={!activeStatus}
          onClick={() => onSelectStatus(undefined)}
        />
        <KpiCard
          label="Sent"
          value={data.sent}
          icon={<FiCheckCircle size={14} />}
          colorPalette="green"
          active={activeStatus === "sent"}
          onClick={() => toggleStatus("sent")}
        />
        <KpiCard
          label="Failed"
          value={data.failed}
          icon={<FiXCircle size={14} />}
          colorPalette="red"
          active={activeStatus === "failed"}
          onClick={() => toggleStatus("failed")}
        />
        <KpiCard
          label="No channel"
          value={data.no_channel ?? 0}
          icon={<FiMinusCircle size={14} />}
          colorPalette="gray"
          active={activeStatus === "no_channel"}
          onClick={() => toggleStatus("no_channel")}
        />
        <KpiCard
          label="Last 24h"
          value={data.last_24h}
          icon={<FiClock size={14} />}
          colorPalette="blue"
        />
      </Grid>

      <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={4}>
        <Box
          borderWidth="1px"
          borderRadius="xl"
          p={4}
          bg="bg.panel"
          shadow="xs"
        >
          <Text fontWeight="semibold" mb={3} fontSize="sm">
            By Severity
          </Text>
          <VStack align="stretch" gap={2.5}>
            {SEVERITY_ORDER.map((sev) => {
              const count =
                data.by_severity.find((s) => s.severity === sev)?.count ?? 0
              const pct =
                data.total > 0 ? Math.round((count / severityTotal) * 100) : 0
              const color = SEVERITY_COLORS[sev] ?? "gray"
              return (
                <Flex key={sev} align="center" gap={3}>
                  <Badge
                    colorPalette={color}
                    variant="subtle"
                    size="sm"
                    w="72px"
                    justifyContent="center"
                    textTransform="capitalize"
                    flexShrink={0}
                  >
                    {sev}
                  </Badge>
                  <Box
                    flex={1}
                    h="6px"
                    bg="bg.muted"
                    borderRadius="full"
                    overflow="hidden"
                  >
                    <Box
                      h="full"
                      w={`${count > 0 ? Math.max(3, pct) : 0}%`}
                      bg={`${color}.solid`}
                      borderRadius="full"
                      transition="width 0.25s ease"
                    />
                  </Box>
                  <Text
                    fontSize="xs"
                    fontWeight="semibold"
                    fontVariantNumeric="tabular-nums"
                    minW="56px"
                    textAlign="right"
                  >
                    {count}{" "}
                    <Text as="span" color="fg.muted" fontWeight="normal">
                      ({pct}%)
                    </Text>
                  </Text>
                </Flex>
              )
            })}
          </VStack>
        </Box>

        <Box
          borderWidth="1px"
          borderRadius="xl"
          p={4}
          bg="bg.panel"
          shadow="xs"
        >
          <Text fontWeight="semibold" mb={3} fontSize="sm">
            Top Rules Fired
          </Text>
          <VStack align="stretch" gap={2.5}>
            {data.by_rule.length === 0 && (
              <Text fontSize="sm" color="fg.muted">
                No alerts fired yet.
              </Text>
            )}
            {data.by_rule.map((r) => {
              const pct = Math.max(
                4,
                Math.round((r.count / maxRuleCount) * 100),
              )
              return (
                <Box key={r.rule_name}>
                  <Flex justify="space-between" align="center" gap={2} mb={1}>
                    <Text
                      fontSize="xs"
                      fontWeight="medium"
                      truncate
                      title={r.rule_name}
                    >
                      {r.rule_name}
                    </Text>
                    <Badge
                      colorPalette="gray"
                      variant="subtle"
                      size="xs"
                      fontVariantNumeric="tabular-nums"
                      flexShrink={0}
                    >
                      {r.count}
                    </Badge>
                  </Flex>
                  <Box
                    h="5px"
                    w="full"
                    bg="bg.muted"
                    borderRadius="full"
                    overflow="hidden"
                  >
                    <Box
                      h="full"
                      w={`${pct}%`}
                      bg="teal.solid"
                      borderRadius="full"
                      transition="width 0.25s ease"
                    />
                  </Box>
                </Box>
              )
            })}
          </VStack>
        </Box>
      </Grid>
    </Box>
  )
}

function AlertEventsTable({
  autoRefreshMs,
  onAutoRefreshChange,
}: {
  autoRefreshMs: number
  onAutoRefreshChange: (ms: number) => void
}) {
  const queryClient = useQueryClient()
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, status } = Route.useSearch()
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)
  const [selected, setSelected] = useState<AlertEventPublic | null>(null)

  const refetchInterval =
    autoRefreshMs > 0 && selected === null ? autoRefreshMs : false

  const { data, isLoading, isFetching, dataUpdatedAt } = useQuery({
    ...getQueryOptions({ page, perPage, status }),
    placeholderData: (prev) => prev,
    refetchInterval,
  })
  const count = data?.count ?? 0

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["alert_events"] })
    queryClient.invalidateQueries({ queryKey: ["alert_statistics"] })
  }

  return (
    <Box>
      <ListToolbar
        mt={0}
        mb={4}
        actions={
          <RefreshControl
            onRefresh={handleRefresh}
            isFetching={isFetching}
            dataUpdatedAt={dataUpdatedAt}
            ariaLabel="Refresh alert history"
            autoRefreshMs={autoRefreshMs}
            onAutoRefreshChange={onAutoRefreshChange}
            autoRefreshPausedReason={
              selected !== null
                ? "Paused while viewing event details"
                : undefined
            }
          />
        }
      >
        <FilterSelect
          value={status}
          onChange={(v) =>
            navigate({ search: (s) => ({ ...s, status: v, page: 1 }) })
          }
          options={STATUS_OPTIONS}
          placeholder="All statuses"
          ariaLabel="Filter by delivery status"
        />
        {!isLoading && (
          <Text fontSize="xs" color="fg.muted" whiteSpace="nowrap">
            {count} {count === 1 ? "event" : "events"}
          </Text>
        )}
      </ListToolbar>

      {isLoading ? (
        <Box
          borderWidth="1px"
          borderRadius="xl"
          p={4}
          bg="bg.panel"
          shadow="sm"
        >
          <VStack align="stretch" gap={3}>
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} h="36px" borderRadius="md" />
            ))}
          </VStack>
        </Box>
      ) : count === 0 ? (
        <Box
          borderWidth="1px"
          borderRadius="xl"
          py={8}
          bg="bg.panel"
          shadow="xs"
        >
          <EmptyState.Root>
            <EmptyState.Content>
              <VStack>
                <EmptyState.Indicator>
                  <FiAlertCircle />
                </EmptyState.Indicator>
                <EmptyState.Title>No alert events</EmptyState.Title>
                <EmptyState.Description>
                  {status
                    ? "No events match the selected delivery status."
                    : "Alerts will appear here when rules are triggered."}
                </EmptyState.Description>
              </VStack>
            </EmptyState.Content>
          </EmptyState.Root>
        </Box>
      ) : (
        <>
          <Box
            borderWidth="1px"
            borderRadius="xl"
            overflow="hidden"
            bg="bg.panel"
            shadow="sm"
          >
            <Box overflowX="auto">
              <Table.Root size="sm">
                <Table.Header bg="bg.muted">
                  <Table.Row>
                    <Table.ColumnHeader whiteSpace="nowrap">
                      Triggered At
                    </Table.ColumnHeader>
                    <Table.ColumnHeader>Rule</Table.ColumnHeader>
                    <Table.ColumnHeader>Summary</Table.ColumnHeader>
                    <Table.ColumnHeader>Severity</Table.ColumnHeader>
                    <Table.ColumnHeader>Channel</Table.ColumnHeader>
                    <Table.ColumnHeader>Status</Table.ColumnHeader>
                    <Table.ColumnHeader w="32px" />
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {data?.data.map((ev) => {
                    const summary = summarizePayload(ev.payload_snapshot)
                    return (
                      <Table.Row
                        key={ev.id}
                        role="button"
                        tabIndex={0}
                        aria-label={`Show details of ${ev.rule_name ?? "alert"}`}
                        cursor="pointer"
                        _hover={{ bg: "bg.muted" }}
                        onClick={() => setSelected(ev)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault()
                            setSelected(ev)
                          }
                        }}
                      >
                        <Table.Cell
                          fontSize="xs"
                          whiteSpace="nowrap"
                          fontVariantNumeric="tabular-nums"
                          color="fg.muted"
                        >
                          {ev.triggered_at
                            ? formatDateTime(ev.triggered_at, {
                                hour12: false,
                              })
                            : "—"}
                        </Table.Cell>
                        <Table.Cell fontWeight="medium" fontSize="sm">
                          <Text
                            truncate
                            maxW="240px"
                            title={ev.rule_name ?? ev.rule_id}
                          >
                            {ev.rule_name ?? ev.rule_id}
                          </Text>
                        </Table.Cell>
                        <Table.Cell fontSize="xs" maxW="300px">
                          {summary ? (
                            <Text truncate color="fg.muted" title={summary}>
                              {summary}
                            </Text>
                          ) : ev.error_message ? (
                            <Text
                              truncate
                              color="red.fg"
                              title={ev.error_message}
                            >
                              {ev.error_message}
                            </Text>
                          ) : (
                            <Text color="fg.muted">—</Text>
                          )}
                        </Table.Cell>
                        <Table.Cell>
                          {ev.rule_severity && (
                            <Badge
                              colorPalette={
                                SEVERITY_COLORS[ev.rule_severity ?? ""] ??
                                "gray"
                              }
                              variant="subtle"
                              size="sm"
                              textTransform="capitalize"
                            >
                              {ev.rule_severity}
                            </Badge>
                          )}
                        </Table.Cell>
                        <Table.Cell>
                          <ChannelCell ev={ev} />
                        </Table.Cell>
                        <Table.Cell>
                          <HStack gap={1.5}>
                            <Badge
                              colorPalette={
                                STATUS_COLORS[ev.status ?? ""] ?? "gray"
                              }
                              variant="subtle"
                              size="sm"
                              whiteSpace="nowrap"
                            >
                              <StatusIcon status={ev.status} />
                              {STATUS_LABELS[ev.status ?? ""] ?? ev.status}
                            </Badge>
                            {ev.error_message && (
                              <Box
                                color="red.fg"
                                title={ev.error_message}
                                flexShrink={0}
                              >
                                <FiAlertTriangle size={13} />
                              </Box>
                            )}
                          </HStack>
                        </Table.Cell>
                        <Table.Cell color="fg.muted" px={2}>
                          <FiChevronRight size={14} />
                        </Table.Cell>
                      </Table.Row>
                    )
                  })}
                </Table.Body>
              </Table.Root>
            </Box>
          </Box>

          <Flex
            justifyContent="space-between"
            align="center"
            mt={4}
            gap={3}
            wrap="wrap"
          >
            <PageSizeSelect
              value={perPage}
              onChange={(v) => {
                setPerPage(v)
                navigate({ search: (s) => ({ ...s, page: 1 }) })
              }}
            />
            <PaginationRoot
              count={count}
              pageSize={perPage}
              page={page}
              onPageChange={(e) =>
                navigate({ search: (s) => ({ ...s, page: e.page }) })
              }
            >
              <Flex>
                <PaginationPrevTrigger />
                <PaginationItems />
                <PaginationNextTrigger />
              </Flex>
            </PaginationRoot>
          </Flex>
        </>
      )}
      <AlertEventDetails event={selected} onClose={() => setSelected(null)} />
    </Box>
  )
}

function AlertEventsPage() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { status } = Route.useSearch()
  const [autoRefreshMs, setAutoRefreshMs] = useState(0)

  return (
    <Container maxW="full" pb={8}>
      <PageHeader
        title="Alert History"
        description="History of all triggered alerts and their delivery status."
        icon={FiAlertTriangle}
      />
      <Box mt={6}>
        <AlertStatisticsPanel
          activeStatus={status}
          onSelectStatus={(nextStatus) =>
            navigate({ search: (s) => ({ ...s, status: nextStatus, page: 1 }) })
          }
          refetchInterval={autoRefreshMs > 0 ? autoRefreshMs : false}
        />
        <AlertEventsTable
          autoRefreshMs={autoRefreshMs}
          onAutoRefreshChange={setAutoRefreshMs}
        />
      </Box>
    </Container>
  )
}
