import {
  Badge,
  Box,
  Container,
  EmptyState,
  Flex,
  Grid,
  Heading,
  Stat,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import { FiAlertCircle } from "react-icons/fi"
import { z } from "zod"

import { type AlertEventPublic, AlertEventsService } from "@/client"
import { AlertEventDetails } from "@/components/AlertEvents/AlertEventDetails"
import { FilterSelect } from "@/components/Common/FilterSelect"
import { ListToolbar } from "@/components/Common/ListToolbar"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"

const DEFAULT_PER_PAGE = 10

const searchSchema = z.object({
  page: z.number().catch(1),
  status: z.string().optional(),
})

const SEVERITY_COLORS: Record<string, string> = {
  low: "blue",
  medium: "yellow",
  high: "orange",
  critical: "red",
}

const STATUS_COLORS: Record<string, string> = {
  sent: "green",
  failed: "red",
  no_channel: "gray",
}

const STATUS_LABELS: Record<string, string> = {
  sent: "sent",
  failed: "failed",
  no_channel: "no channel",
}

const STATUS_OPTIONS = [
  { value: "sent", label: "Sent" },
  { value: "failed", label: "Failed" },
  { value: "no_channel", label: "No channel" },
]

function ChannelCell({ ev }: { ev: AlertEventPublic }) {
  if (ev.channel_name) return <>{ev.channel_name}</>
  return (
    <Text as="span" color="fg.muted" fontStyle="italic">
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

function AlertEventsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, status } = Route.useSearch()
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)
  const [selected, setSelected] = useState<AlertEventPublic | null>(null)

  const { data, isLoading } = useQuery(
    getQueryOptions({ page, perPage, status }),
  )
  const count = data?.count ?? 0

  if (isLoading) return <Text>Loading...</Text>

  return (
    <Box>
      <ListToolbar mt={0} mb={4}>
        <FilterSelect
          value={status}
          onChange={(v) =>
            navigate({ search: (s) => ({ ...s, status: v, page: 1 }) })
          }
          options={STATUS_OPTIONS}
          placeholder="All statuses"
          ariaLabel="Filter by delivery status"
        />
      </ListToolbar>

      {count === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <VStack>
              <EmptyState.Indicator>
                <FiAlertCircle />
              </EmptyState.Indicator>
              <EmptyState.Title>No alert events</EmptyState.Title>
              <EmptyState.Description>
                Alerts will appear here when rules are triggered.
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Triggered At</Table.ColumnHeader>
                <Table.ColumnHeader>Rule</Table.ColumnHeader>
                <Table.ColumnHeader>Severity</Table.ColumnHeader>
                <Table.ColumnHeader>Channel</Table.ColumnHeader>
                <Table.ColumnHeader>Status</Table.ColumnHeader>
                <Table.ColumnHeader>Error</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {data?.data.map((ev) => (
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
                  <Table.Cell fontSize="xs" whiteSpace="nowrap">
                    {ev.triggered_at
                      ? new Date(ev.triggered_at).toLocaleString("en-US", {
                          hour12: false,
                        })
                      : "—"}
                  </Table.Cell>
                  <Table.Cell fontWeight="medium">
                    {ev.rule_name ?? ev.rule_id}
                  </Table.Cell>
                  <Table.Cell>
                    {ev.rule_severity && (
                      <Badge
                        colorPalette={
                          SEVERITY_COLORS[ev.rule_severity ?? ""] ?? "gray"
                        }
                      >
                        {ev.rule_severity}
                      </Badge>
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    <ChannelCell ev={ev} />
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      colorPalette={STATUS_COLORS[ev.status ?? ""] ?? "gray"}
                    >
                      {STATUS_LABELS[ev.status ?? ""] ?? ev.status}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell fontSize="xs" color="fg.muted" maxW="200px">
                    <Text truncate>{ev.error_message ?? "—"}</Text>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>

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

const SEVERITY_ORDER = ["critical", "high", "medium", "low"]

function AlertStatisticsPanel() {
  const { data } = useQuery({
    queryFn: () => AlertEventsService.readAlertStatistics(),
    queryKey: ["alert_statistics"],
  })

  if (!data) return null

  return (
    <Box mb={8}>
      <Grid
        templateColumns={{ base: "repeat(2, 1fr)", md: "repeat(5, 1fr)" }}
        gap={4}
        mb={6}
      >
        {[
          { label: "Total Alerts", value: data.total },
          { label: "Sent", value: data.sent },
          { label: "Failed", value: data.failed },
          { label: "No channel", value: data.no_channel ?? 0 },
          { label: "Last 24h", value: data.last_24h },
        ].map(({ label, value }) => (
          <Box key={label} borderWidth="1px" borderRadius="lg" p={4}>
            <Stat.Root>
              <Stat.Label color="fg.muted" fontSize="xs">
                {label}
              </Stat.Label>
              <Stat.ValueText fontSize="2xl" fontWeight="bold">
                {value}
              </Stat.ValueText>
            </Stat.Root>
          </Box>
        ))}
      </Grid>

      <Grid templateColumns={{ base: "1fr", md: "1fr 1fr" }} gap={4}>
        <Box borderWidth="1px" borderRadius="lg" p={4}>
          <Text fontWeight="semibold" mb={3} fontSize="sm">
            By Severity
          </Text>
          <VStack align="stretch" gap={2}>
            {SEVERITY_ORDER.map((sev) => {
              const item = data.by_severity.find((s) => s.severity === sev)
              return (
                <Flex key={sev} justify="space-between" align="center">
                  <Badge
                    colorPalette={SEVERITY_COLORS[sev] ?? "gray"}
                    size="sm"
                  >
                    {sev}
                  </Badge>
                  <Text fontSize="sm" fontWeight="medium">
                    {item?.count ?? 0}
                  </Text>
                </Flex>
              )
            })}
          </VStack>
        </Box>

        <Box borderWidth="1px" borderRadius="lg" p={4}>
          <Text fontWeight="semibold" mb={3} fontSize="sm">
            Top Rules Fired
          </Text>
          <VStack align="stretch" gap={2}>
            {data.by_rule.length === 0 && (
              <Text fontSize="sm" color="fg.muted">
                No data
              </Text>
            )}
            {data.by_rule.map((r) => (
              <Flex key={r.rule_name} justify="space-between" align="center">
                <Text fontSize="sm" truncate maxW="70%">
                  {r.rule_name}
                </Text>
                <Badge colorPalette="gray" size="sm">
                  {r.count}
                </Badge>
              </Flex>
            ))}
          </VStack>
        </Box>
      </Grid>
    </Box>
  )
}

function AlertEventsPage() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12} pb={4}>
        Alert History
      </Heading>
      <Text color="fg.muted" mb={6}>
        History of all triggered alerts and their delivery status.
      </Text>
      <AlertStatisticsPanel />
      <AlertEventsTable />
    </Container>
  )
}
