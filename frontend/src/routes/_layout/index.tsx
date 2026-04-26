import { Chart, useChart } from "@chakra-ui/charts"
import {
  Badge,
  Box,
  Button,
  Container,
  Flex,
  Grid,
  GridItem,
  Heading,
  Input,
  Skeleton,
  Spinner,
  Stat,
  Table,
  Text,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { Link, createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import type { CancelablePromise } from "@/client"
import {
  AaaStatisticsService,
  AuditLogsService,
  HostsService,
  ProfilesService,
  RulesetsService,
  TacacsGroupsService,
  TacacsLogsService,
  TacacsUsersService,
} from "@/client"
import type { AuditLogPublic } from "@/client"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
})

// ─── constants ────────────────────────────────────────────────────────────────

const CHART_COLORS = ["blue.500", "green.500", "pink.500", "orange.500", "red.500"]
const FAIL_COLORS = ["red.500", "orange.500", "pink.500", "yellow.500", "purple.500"]

const ACTION_COLOR: Record<string, string> = {
  CREATE: "green",
  UPDATE: "blue",
  DELETE: "red",
  LOGIN_SUCCESS: "teal",
  LOGIN_FAILED: "orange",
}

const AREA_SERIES = [
  { key: "Auth Success", color: "green" },
  { key: "Auth Fail", color: "red" },
  { key: "Authz Permit", color: "blue" },
  { key: "Authz Deny", color: "orange" },
  { key: "Acct Start", color: "purple" },
  { key: "Acct Stop", color: "gray" },
]

// ─── types & filter helpers ───────────────────────────────────────────────────

type FilterMode = "7d" | "30d" | "custom"

const FILTER_LABELS: Record<FilterMode, string> = {
  "7d": "Last 7 Days",
  "30d": "Last 30 Days",
  custom: "Date Range",
}

const TREND_LABEL: Record<FilterMode, string> = {
  "7d": "Last 7 Days AAA Trend",
  "30d": "Last 30 Days AAA Trend",
  custom: "AAA Trend — Custom Range",
}

function getRangeDate(
  mode: FilterMode,
  customStart: string,
  customEnd: string,
): string | undefined {
  const fmt = (d: Date) => d.toISOString().split("T")[0]
  const today = new Date()
  // Statistics are aggregated from completed log files — today is never in the DB.
  // Always cap the end date at yesterday to avoid a trailing zero on the chart.
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  const end = fmt(yesterday)
  if (mode === "7d") {
    const s = new Date(yesterday)
    s.setDate(yesterday.getDate() - 6)
    return `${fmt(s)},${end}`
  }
  if (mode === "30d") {
    const s = new Date(yesterday)
    s.setDate(yesterday.getDate() - 29)
    return `${fmt(s)},${end}`
  }
  if (customStart && customEnd) return `${customStart},${customEnd}`
  return undefined
}

// ─── helpers ──────────────────────────────────────────────────────────────────

interface PieData {
  name: string
  value: number
  color: string
}



function buildRangeTrendData(stats: any) {
  if (!stats?.last_range_days_authentication_success) return []
  const toMap = (arr: any[]) =>
    Object.fromEntries(arr.map((d: any) => [d.date, d.count]))
  const authSuccess = toMap(stats.last_range_days_authentication_success)
  const authFail = toMap(stats.last_range_days_authentication_fail ?? [])
  const authzPermit = toMap(stats.last_range_days_authorization_permit ?? [])
  const authzDeny = toMap(stats.last_range_days_authorization_deny ?? [])
  const acctStart = toMap(stats.last_range_days_accounting_start ?? [])
  const acctStop = toMap(stats.last_range_days_accounting_stop ?? [])
  return (stats.last_range_days_authentication_success as any[]).map((d: any) => ({
    date: new Date(d.date + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    "Auth Success": authSuccess[d.date] ?? 0,
    "Auth Fail": authFail[d.date] ?? 0,
    "Authz Permit": authzPermit[d.date] ?? 0,
    "Authz Deny": authzDeny[d.date] ?? 0,
    "Acct Start": acctStart[d.date] ?? 0,
    "Acct Stop": acctStop[d.date] ?? 0,
  }))
}


// ─── sub-components ───────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: number | undefined
  highlight?: "danger" | "success" | "none"
}

function StatCard({ label, value, highlight = "none" }: StatCardProps) {
  const valueColor =
    highlight === "danger" && (value ?? 0) > 0
      ? "red.500"
      : highlight === "success"
        ? "green.500"
        : undefined
  return (
    <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
      <Stat.Root>
        <Stat.Label fontSize="sm" color="fg.muted">
          {label}
        </Stat.Label>
        <Stat.ValueText fontSize="3xl" fontWeight="bold" color={valueColor}>
          {value ?? 0}
        </Stat.ValueText>
      </Stat.Root>
    </Box>
  )
}

function StatPie({ title, data }: { title: string; data: PieData[] }) {
  const chart = useChart({ data })
  return (
    <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
      <Heading size="sm" mb={3}>
        {title}
      </Heading>
      {data.length === 0 ? (
        <Flex direction="column" align="center" justify="center" h="160px" gap={1}>
          <Text fontSize="2xl">📭</Text>
          <Text color="fg.muted" fontSize="sm" fontWeight="medium">No activity</Text>
          <Text color="fg.subtle" fontSize="xs" textAlign="center">No records for selected period</Text>
        </Flex>
      ) : (
        <Chart.Root mx="auto" maxH="220px" chart={chart}>
          <PieChart>
            <Tooltip cursor={false} animationDuration={100} content={<Chart.Tooltip hideLabel />} />
            <Legend content={<Chart.Legend />} />
            <Pie
              isAnimationActive={false}
              data={chart.data}
              dataKey={chart.key("value")}
              label={({ value }) => `${value}`}
              labelLine={false}
            >
              {chart.data.map((item, i) => (
                <Cell key={item.name ?? i} fill={chart.color(item.color)} />
              ))}
            </Pie>
          </PieChart>
        </Chart.Root>
      )}
    </Box>
  )
}

function SectionHeading({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <Flex align="center" justify="space-between" mb={3}>
      <Heading size="md">{children}</Heading>
      {action}
    </Flex>
  )
}

function FilterBar({
  mode,
  onMode,
  customStart,
  customEnd,
  onCustomStart,
  onCustomEnd,
}: {
  mode: FilterMode
  onMode: (m: FilterMode) => void
  customStart: string
  customEnd: string
  onCustomStart: (s: string) => void
  onCustomEnd: (s: string) => void
}) {
  return (
    <Flex gap={3} flexWrap="wrap" align="center">
      {/* Mode buttons — always visible */}
      <Flex gap={2} align="center" flexShrink={0}>
        {(["7d", "30d", "custom"] as FilterMode[]).map((m) => (
          <Button
            key={m}
            size="sm"
            variant={mode === m ? "solid" : "outline"}
            colorPalette={mode === m ? "blue" : "gray"}
            onClick={() => onMode(m)}
          >
            {FILTER_LABELS[m]}
          </Button>
        ))}
      </Flex>

      {/* Date pickers — shown only in custom mode, always on one line */}
      {mode === "custom" && (
        <Flex gap={2} align="center" flexShrink={0}>
          <Input
            size="sm"
            type="date"
            value={customStart}
            onChange={(e) => onCustomStart(e.target.value)}
            maxW="160px"
            minW="130px"
          />
          <Text fontSize="sm" color="fg.muted" whiteSpace="nowrap">to</Text>
          <Input
            size="sm"
            type="date"
            value={customEnd}
            onChange={(e) => onCustomEnd(e.target.value)}
            maxW="160px"
            minW="130px"
          />
        </Flex>
      )}
    </Flex>
  )
}

// ─── Today's TACACS Log Summary ───────────────────────────────────────────────

function TodayLogSummary() {
  const { data, isLoading } = useQuery({
    queryKey: ["tacacs_log_summary_today"],
    queryFn: () => TacacsLogsService.getLogEventsSummary(),
  })

  const cards = [
    {
      label: "Authentication",
      badges: [
        { label: `✓ ${data?.authentication.success ?? 0} success`, color: "green" },
        { label: `✗ ${data?.authentication.failed ?? 0} failed`, color: "red" },
      ],
    },
    {
      label: "Authorization",
      badges: [
        { label: `✓ ${data?.authorization.permit ?? 0} permit`, color: "teal" },
        { label: `✗ ${data?.authorization.deny ?? 0} deny`, color: "orange" },
      ],
    },
    {
      label: "Accounting",
      badges: [
        { label: `▶ ${data?.accounting.start ?? 0} start`, color: "blue" },
        { label: `■ ${data?.accounting.stop ?? 0} stop`, color: "gray" },
      ],
    },
  ]

  return (
    <GridItem colSpan={{ base: 1, sm: 2, md: 4 }}>
      <SectionHeading
        action={
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          <Link to={"/tacacs_logs" as any}>
            <Text fontSize="sm" color="blue.500">View logs →</Text>
          </Link>
        }
      >
        Today's TACACS Log Summary
      </SectionHeading>
      <Grid templateColumns={{ base: "1fr", sm: "repeat(3, 1fr)" }} gap={4}>
        {cards.map(({ label, badges }) => (
          <Box key={label} p={4} borderWidth="1px" borderRadius="lg">
            <Text fontWeight="semibold" mb={2} fontSize="sm" color="fg.muted">
              {label}
            </Text>
            {isLoading ? (
              <Skeleton height="24px" />
            ) : (
              <Flex gap={2} flexWrap="wrap">
                {badges.map((b) => (
                  <Badge key={b.label} colorPalette={b.color} size="md">
                    {b.label}
                  </Badge>
                ))}
              </Flex>
            )}
          </Box>
        ))}
      </Grid>
    </GridItem>
  )
}

// ─── Config Overview ──────────────────────────────────────────────────────────

interface ConfigItem {
  label: string
  to: string
  queryKey: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  fn: () => CancelablePromise<any>
}

const CONFIG_ITEMS: ConfigItem[] = [
  { label: "Hosts", to: "/hosts", queryKey: "config_count_hosts", fn: () => HostsService.readHosts({ limit: 1 }) },
  { label: "Users", to: "/tacacs_users", queryKey: "config_count_users", fn: () => TacacsUsersService.readTacacsUsers({ limit: 1 }) },
  { label: "Groups", to: "/tacacs_groups", queryKey: "config_count_groups", fn: () => TacacsGroupsService.readTacacsGroups({ limit: 1 }) },
  { label: "Profiles", to: "/profiles", queryKey: "config_count_profiles", fn: () => ProfilesService.readProfiles({ limit: 1 }) },
  { label: "Rulesets", to: "/rulesets", queryKey: "config_count_rulesets", fn: () => RulesetsService.readRulesets({ limit: 1 }) },
]

function ConfigCountCard({ label, to, queryKey, fn }: ConfigItem) {
  const { data, isLoading } = useQuery({ queryKey: [queryKey], queryFn: fn })
  return (
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    <Link to={to as any}>
      <Box
        p={4}
        borderWidth="1px"
        borderRadius="lg"
        h="100%"
        cursor="pointer"
        _hover={{ borderColor: "blue.400", shadow: "sm" }}
        transition="all 0.15s"
      >
        <Stat.Root>
          <Stat.Label fontSize="sm" color="fg.muted">
            {label}
          </Stat.Label>
          {isLoading ? (
            <Skeleton height="36px" mt={1} />
          ) : (
            <Stat.ValueText fontSize="3xl" fontWeight="bold">
              {data?.count ?? 0}
            </Stat.ValueText>
          )}
        </Stat.Root>
      </Box>
    </Link>
  )
}

function ConfigOverview() {
  return (
    <GridItem colSpan={{ base: 1, sm: 2, md: 4 }}>
      <SectionHeading>TACACS Config Overview</SectionHeading>
      <Grid
        templateColumns={{
          base: "repeat(2, 1fr)",
          sm: "repeat(3, 1fr)",
          md: "repeat(5, 1fr)",
        }}
        gap={4}
      >
        {CONFIG_ITEMS.map((item) => (
          <ConfigCountCard key={item.label} {...item} />
        ))}
      </Grid>
    </GridItem>
  )
}

// ─── Recent Activity ──────────────────────────────────────────────────────────

function RecentActivity() {
  const { data, isLoading } = useQuery({
    queryKey: ["recent_audit_logs"],
    queryFn: () => AuditLogsService.readAuditLogs({ limit: 10 }),
  })

  const logs = data?.data ?? []

  return (
    <GridItem colSpan={{ base: 1, sm: 2, md: 4 }}>
      <SectionHeading
        action={
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          <Link to={"/audit_logs" as any}>
            <Text fontSize="sm" color="blue.500">View all →</Text>
          </Link>
        }
      >
        Recent User Activity
      </SectionHeading>
      {isLoading ? (
        <Spinner size="sm" />
      ) : logs.length === 0 ? (
        <Text color="fg.muted" fontSize="sm">
          No recent activity.
        </Text>
      ) : (
        <Box borderWidth="1px" borderRadius="lg" overflow="hidden">
          <Table.Root size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Time</Table.ColumnHeader>
                <Table.ColumnHeader>User</Table.ColumnHeader>
                <Table.ColumnHeader>Action</Table.ColumnHeader>
                <Table.ColumnHeader>Entity</Table.ColumnHeader>
                <Table.ColumnHeader>Description</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {logs.map((log: AuditLogPublic) => (
                <Table.Row key={log.id}>
                  <Table.Cell whiteSpace="nowrap" fontSize="xs" color="fg.muted">
                    {new Date(log.created_at).toLocaleString()}
                  </Table.Cell>
                  <Table.Cell fontSize="xs" maxW="32" truncate>
                    {log.user_email}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      colorPalette={ACTION_COLOR[log.action] ?? "gray"}
                      size="sm"
                    >
                      {log.action}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell fontSize="xs">
                    {log.entity_type}
                    {log.entity_id ? ` #${log.entity_id.slice(0, 8)}` : ""}
                  </Table.Cell>
                  <Table.Cell fontSize="xs" maxW="48" truncate color="fg.muted">
                    {log.description ?? "—"}
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Box>
      )}
    </GridItem>
  )
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

function Dashboard() {
  const [filterMode, setFilterMode] = useState<FilterMode>("7d")
  const [customStart, setCustomStart] = useState("")
  const [customEnd, setCustomEnd] = useState("")

  const rangeDate = getRangeDate(filterMode, customStart, customEnd)

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ["aaa_statistics"],
    queryFn: () => AaaStatisticsService.readAaaStatistics(),
  })

  const { data: rangeStats, isLoading: rangeLoading } = useQuery({
    queryKey: ["aaa_statistics_range", rangeDate],
    queryFn: () => AaaStatisticsService.readAaaStatisticsRange({ rangeDate }),
    enabled: !!rangeDate,
  })

  const chartsLoading = rangeLoading

  const pieSuccessByUser: PieData[] =
    (rangeStats?.authentication_success_count_by_user ?? []).map((u: any, i: number) => ({
      name: String(u.username ?? ""), value: Number(u.success_count ?? 0), color: CHART_COLORS[i % CHART_COLORS.length],
    }))

  const pieSuccessByIp: PieData[] =
    (rangeStats?.authentication_success_count_by_user_source_ip ?? []).map((u: any, i: number) => ({
      name: String(u.user_source_ip ?? ""), value: Number(u.success_count ?? 0), color: CHART_COLORS[i % CHART_COLORS.length],
    }))

  const pieSuccessByNas: PieData[] =
    (rangeStats?.authentication_success_count_by_nas_ip ?? []).map((u: any, i: number) => ({
      name: String(u.nas_ip ?? ""), value: Number(u.success_count ?? 0), color: CHART_COLORS[i % CHART_COLORS.length],
    }))

  const pieFailedByUser: PieData[] =
    (rangeStats?.authentication_failed_count_by_user ?? []).map((u: any, i: number) => ({
      name: String(u.username ?? ""), value: Number(u.fail_count ?? 0), color: FAIL_COLORS[i % FAIL_COLORS.length],
    }))

  const trendData = buildRangeTrendData(rangeStats)
  const trendEmpty = trendData.length === 0

  return (
    <Container maxW="full" py={8}>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">Dashboard</Heading>
        <Text color="fg.muted" fontSize="sm">
          {new Date().toISOString().split("T")[0]}
        </Text>
      </Flex>

      {isLoading ? (
        <Flex justify="center" align="center" height="50vh">
          <Spinner size="xl" />
        </Flex>
      ) : error ? (
        <Box p={4} borderWidth="1px" borderRadius="lg" borderColor="red.200">
          <Text color="red.500">Error fetching statistics: {error.message}</Text>
        </Box>
      ) : (
        <Grid
          templateColumns={{ base: "1fr", sm: "repeat(2, 1fr)", md: "repeat(4, 1fr)" }}
          gap={6}
        >
          {/* AAA today stat cards — always today */}
          <GridItem>
            <StatCard label="Today Auth Success" value={stats?.today_successful_logins} highlight="success" />
          </GridItem>
          <GridItem>
            <StatCard label="Today Auth Failed" value={stats?.today_failed_logins} highlight="danger" />
          </GridItem>
          <GridItem>
            <StatCard label="Unique Source IPs" value={stats?.today_unique_user_source_ip_count} />
          </GridItem>
          <GridItem>
            <StatCard label="Unique NAS IPs" value={stats?.today_unique_nas_ip_count} />
          </GridItem>

          {/* Today's log summary (auth + authz + acct) */}
          <TodayLogSummary />

          {/* TACACS config entity counts */}
          <ConfigOverview />

          {/* Top 5 & Trend section header with filter */}
          <GridItem colSpan={{ base: 1, sm: 2, md: 4 }}>
            <Box p={4} borderWidth="1px" borderRadius="lg" bg="bg.subtle">
              <Flex align="center" justify="space-between" flexWrap="wrap" gap={3}>
                <Box>
                  <Heading size="sm">Top 5 & AAA Trend</Heading>
                  <Text fontSize="xs" color="fg.muted" mt={0.5}>
                    {filterMode === "custom" && customStart && customEnd
                      ? `${customStart} → ${customEnd}`
                      : filterMode === "custom"
                        ? "Select start and end date"
                        : FILTER_LABELS[filterMode]}
                  </Text>
                </Box>
                <FilterBar
                  mode={filterMode}
                  onMode={setFilterMode}
                  customStart={customStart}
                  customEnd={customEnd}
                  onCustomStart={setCustomStart}
                  onCustomEnd={setCustomEnd}
                />
              </Flex>
            </Box>
          </GridItem>

          {/* Top 5 pie charts */}
          {chartsLoading ? (
            <GridItem colSpan={{ base: 1, sm: 2, md: 4 }}>
              <Flex justify="center" py={8}><Spinner size="md" /></Flex>
            </GridItem>
          ) : (
            <>
              <GridItem>
                <StatPie title="Top 5 Users — Success" data={pieSuccessByUser} />
              </GridItem>
              <GridItem>
                <StatPie title="Top 5 Source IPs" data={pieSuccessByIp} />
              </GridItem>
              <GridItem>
                <StatPie title="Top 5 NAS IPs" data={pieSuccessByNas} />
              </GridItem>
              <GridItem>
                <StatPie title="Top 5 Users — Failed" data={pieFailedByUser} />
              </GridItem>
            </>
          )}

          {/* Trend chart */}
          <GridItem colSpan={{ base: 1, sm: 2, md: 4 }}>
            <Box p={4} borderWidth="1px" borderRadius="lg">
              <Flex align="center" justify="space-between" mb={4}>
                <Heading size="sm">{TREND_LABEL[filterMode]}</Heading>
              </Flex>
              {chartsLoading ? (
                <Flex justify="center" py={8}><Spinner size="md" /></Flex>
              ) : trendEmpty ? (
                <Flex direction="column" align="center" justify="center" h="200px" gap={2}>
                  <Text fontSize="2xl">📈</Text>
                  <Text color="fg.muted" fontSize="sm" fontWeight="medium">No trend data</Text>
                  <Text color="fg.subtle" fontSize="xs">Statistics aggregate periodically — try a wider range</Text>
                </Flex>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    {AREA_SERIES.map(({ key, color }) => (
                      <Line
                        key={key}
                        dataKey={key}
                        type="monotone"
                        stroke={`var(--chakra-colors-${color}-500)`}
                        dot={false}
                        activeDot={{ r: 4 }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              )}
            </Box>
          </GridItem>

          {/* Recent user activity */}
          <RecentActivity />
        </Grid>
      )}
    </Container>
  )
}
