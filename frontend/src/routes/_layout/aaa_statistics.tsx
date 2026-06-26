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
  NativeSelect,
  Spinner,
  Stat,
  Tabs,
  Text,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import {
  FiActivity,
  FiBarChart2,
  FiCalendar,
  FiGlobe,
  FiInbox,
  FiRefreshCw,
  FiServer,
  FiShield,
  FiShieldOff,
} from "react-icons/fi"
import {
  CartesianGrid,
  LabelList,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Sector,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import type { AaaStatisticsDateRangePublic, ApiError } from "@/client"
import { AaaStatisticsService } from "@/client"
import PageHeader from "@/components/Common/PageHeader"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/aaa_statistics")({
  component: AaaStatistics,
})

// ─── Constants ───────────────────────────────────────────────────────────

const CHART_COLORS = [
  "blue.500",
  "green.500",
  "pink.500",
  "orange.500",
  "red.500",
]
const FAIL_COLORS = [
  "red.500",
  "orange.500",
  "pink.500",
  "yellow.500",
  "purple.500",
]
const NODE_COLORS = [
  "teal.500",
  "blue.500",
  "purple.500",
  "pink.500",
  "orange.500",
]

const getISODateString = (date: Date): string =>
  date.toISOString().split("T")[0]

const today = new Date()
const yesterday = new Date(today)
yesterday.setDate(yesterday.getDate() - 1)
const sevenDaysAgo = new Date(today)
sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)

function sumField(list: { count?: number }[] | undefined): number {
  return (list ?? []).reduce((s, d) => s + (d.count ?? 0), 0)
}

// ─── Interfaces & Shared Sub-components ──────────────────────────────────

interface StatCardProps {
  label: string
  value: number | undefined
  highlight?: "danger" | "success" | "none" | "info" | "warning"
}

function StatCard({ label, value, highlight = "none" }: StatCardProps) {
  let Icon = FiActivity
  let colorPalette = "teal"
  let borderLeftColor = "teal.500"

  if (highlight === "success") {
    Icon = FiShield
    colorPalette = "green"
    borderLeftColor = "green.500"
  } else if (highlight === "danger") {
    Icon = FiShieldOff
    colorPalette = "red"
    borderLeftColor = "red.500"
  } else if (highlight === "info") {
    Icon = FiGlobe
    colorPalette = "blue"
    borderLeftColor = "blue.500"
  } else if (highlight === "warning") {
    Icon = FiServer
    colorPalette = "orange"
    borderLeftColor = "orange.500"
  } else if (label.toLowerCase().includes("source")) {
    Icon = FiGlobe
    colorPalette = "purple"
    borderLeftColor = "purple.500"
  } else if (label.toLowerCase().includes("nas")) {
    Icon = FiServer
    colorPalette = "blue"
    borderLeftColor = "blue.500"
  }

  return (
    <Box
      p={5}
      bg="bg.panel"
      borderWidth="1px"
      borderLeftWidth="4px"
      borderLeftColor={borderLeftColor}
      borderRadius="xl"
      shadow="sm"
      transition="all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
      _hover={{
        shadow: "md",
        borderColor: borderLeftColor,
        transform: "translateY(-4px)",
      }}
      h="100%"
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
          <Stat.ValueText
            fontSize="3xl"
            fontWeight="extrabold"
            mt={2}
            fontFamily="mono"
          >
            {value ?? 0}
          </Stat.ValueText>
        </Stat.Root>
        <Box
          p={3}
          bg={`${colorPalette}.muted`}
          color={`${colorPalette}.fg`}
          borderRadius="lg"
          shadow="xs"
        >
          <Icon fontSize="22px" />
        </Box>
      </Flex>
    </Box>
  )
}

interface PieData {
  name: string
  value: number
  color: string
}

function StatPie({ title, data }: { title: string; data: PieData[] }) {
  const chart = useChart({ data: data })

  return (
    <Box
      p={5}
      bg="bg.panel"
      borderWidth="1px"
      borderRadius="xl"
      shadow="sm"
      transition="all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
      _hover={{
        borderColor: "teal.500",
        shadow: "md",
        transform: "translateY(-4px)",
      }}
      h="100%"
    >
      <Heading size="sm" mb={4} fontWeight="bold">
        {title}
      </Heading>
      {data.length === 0 ? (
        <Flex
          direction="column"
          align="center"
          justify="center"
          h="180px"
          gap={2}
        >
          <Box p={3} bg="bg.muted" borderRadius="full" color="fg.subtle">
            <FiInbox fontSize="20px" />
          </Box>
          <Text color="fg.muted" fontSize="sm" fontWeight="semibold">
            No activity
          </Text>
          <Text color="fg.subtle" fontSize="xs" textAlign="center">
            No records for selected node
          </Text>
        </Flex>
      ) : (
        <Chart.Root boxSize="200px" mx="auto" chart={chart}>
          <PieChart responsive>
            <Tooltip
              cursor={false}
              animationDuration={100}
              content={<Chart.Tooltip hideLabel />}
            />
            <Legend content={<Chart.Legend />} />
            <Pie
              isAnimationActive={false}
              data={chart.data}
              dataKey={chart.key("value")}
              shape={(props) => (
                <Sector {...props} fill={chart.color(props.payload!.color)} />
              )}
            >
              <LabelList position="inside" fill="white" stroke="none" />
            </Pie>
          </PieChart>
        </Chart.Root>
      )}
    </Box>
  )
}

// ─── Sub-tabs ────────────────────────────────────────────────────────────

function TodayStatsTab() {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const [selectedNode, setSelectedNode] = useState<string>("")

  const { data: nodes } = useQuery({
    queryKey: ["aaa_nodes"],
    queryFn: () => AaaStatisticsService.listAaaNodes(),
  })

  const {
    data: stats,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["aaa_statistics", selectedNode],
    queryFn: () =>
      AaaStatisticsService.readAaaStatistics({
        nodeName: selectedNode || undefined,
      }),
    refetchInterval: 5 * 60 * 1000, // refresh every 5 minutes
  })

  const runMutation = useMutation({
    mutationFn: () => AaaStatisticsService.runAaaStatistics(),
    onSuccess: () => {
      showSuccessToast("Statistics updated successfully.")
      queryClient.invalidateQueries({ queryKey: ["aaa_statistics"] })
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
  })

  const data_authentication_success_count_by_user =
    stats?.today_authentication_success_count_by_user?.map(
      (user: any, index) => ({
        name: (user.username as string) || "",
        value: (user.success_count as number) || 0,
        color: CHART_COLORS[index % CHART_COLORS.length],
      }),
    ) || []

  const data_authentication_success_count_by_user_source_ip =
    stats?.today_authentication_success_count_by_user_source_ip?.map(
      (user: any, index) => ({
        name: (user.user_source_ip as string) || "",
        value: (user.success_count as number) || 0,
        color: CHART_COLORS[index % CHART_COLORS.length],
      }),
    ) || []

  const data_authentication_success_count_by_nas_ip =
    stats?.today_authentication_success_count_by_nas_ip?.map(
      (user: any, index) => ({
        name: (user.nas_ip as string) || "",
        value: (user.success_count as number) || 0,
        color: CHART_COLORS[index % CHART_COLORS.length],
      }),
    ) || []

  const data_authentication_failed_count_by_user =
    stats?.today_authentication_failed_count_by_user?.map(
      (user: any, index) => ({
        name: (user.username as string) || "",
        value: (user.fail_count as number) || 0,
        color: FAIL_COLORS[index % FAIL_COLORS.length],
      }),
    ) || []

  const last_7_days_data =
    stats?.last_7_days_authentication_success?.map((item, index) => ({
      date: new Date(item.date as string).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      "Auth Success": item.count,
      "Auth Fail": stats?.last_7_days_authentication_fail?.[index]?.count || 0,
      "Authz Permit":
        stats?.last_7_days_authorization_permit?.[index]?.count || 0,
      "Authz Deny": stats?.last_7_days_authorization_deny?.[index]?.count || 0,
      "Acct Start": stats?.last_7_days_accounting_start?.[index]?.count || 0,
      "Acct Stop": stats?.last_7_days_accounting_stop?.[index]?.count || 0,
    })) || []

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6} gap={4} wrap="wrap">
        <Heading size="md" fontWeight="bold">
          Today's Activity
        </Heading>
        <Flex align="center" gap={3}>
          <NativeSelect.Root size="sm" width="160px">
            <NativeSelect.Field
              value={selectedNode}
              onChange={(e) => setSelectedNode(e.target.value)}
            >
              <option value="">All Nodes</option>
              {(nodes ?? []).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
          <Button
            size="sm"
            onClick={() => runMutation.mutate()}
            loading={runMutation.isPending}
            variant="outline"
            colorPalette="teal"
          >
            <FiRefreshCw style={{ marginRight: "6px" }} />
            Run Statistics Now
          </Button>
        </Flex>
      </Flex>

      {isLoading ? (
        <Flex justify="center" align="center" height="40vh">
          <Spinner size="xl" />
        </Flex>
      ) : error ? (
        <Box p={4} borderWidth="1px" borderRadius="lg" borderColor="red.200">
          <Text color="red.500">
            Error fetching statistics: {error.message}
          </Text>
        </Box>
      ) : (
        <Grid
          templateColumns={{
            base: "1fr",
            md: "repeat(2, 1fr)",
            xl: "repeat(4, 1fr)",
          }}
          gap={6}
        >
          {/* Top Stat Cards */}
          <GridItem>
            <StatCard
              label="Today Successful Logins"
              value={stats?.today_successful_logins}
              highlight="success"
            />
          </GridItem>
          <GridItem>
            <StatCard
              label="Today Unique IP Users"
              value={stats?.today_unique_user_source_ip_count}
            />
          </GridItem>
          <GridItem>
            <StatCard
              label="Today Unique NAS IP"
              value={stats?.today_unique_nas_ip_count}
            />
          </GridItem>
          <GridItem>
            <StatCard
              label="Today Failed Logins"
              value={stats?.today_failed_logins}
              highlight="danger"
            />
          </GridItem>

          {/* Top 5 Charts */}
          <GridItem colSpan={{ base: 1, md: 2, xl: 1 }}>
            <StatPie
              title="Top 5 Users Login Success"
              data={data_authentication_success_count_by_user}
            />
          </GridItem>
          <GridItem colSpan={{ base: 1, md: 2, xl: 1 }}>
            <StatPie
              title="Top 5 Source IPs"
              data={data_authentication_success_count_by_user_source_ip}
            />
          </GridItem>
          <GridItem colSpan={{ base: 1, md: 2, xl: 1 }}>
            <StatPie
              title="Top 5 NAS IPs"
              data={data_authentication_success_count_by_nas_ip}
            />
          </GridItem>
          <GridItem colSpan={{ base: 1, md: 2, xl: 1 }}>
            <StatPie
              title="Top 5 Users Login Failed"
              data={data_authentication_failed_count_by_user}
            />
          </GridItem>

          {/* Trend Chart */}
          <GridItem colSpan={{ base: 1, md: 2, xl: 4 }}>
            <Box
              p={5}
              bg="bg.panel"
              borderWidth="1px"
              borderRadius="xl"
              shadow="sm"
              transition="all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
              _hover={{
                borderColor: "teal.500",
                shadow: "md",
                transform: "translateY(-4px)",
              }}
              h="100%"
            >
              <Heading size="sm" mb={4} fontWeight="bold">
                Last 7 Days AAA Statistics
              </Heading>
              <ResponsiveContainer width="100%" height={350}>
                <LineChart
                  data={last_7_days_data}
                  margin={{ top: 10, right: 30, left: -20, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--chakra-colors-border)"
                  />
                  <XAxis
                    dataKey="date"
                    tick={{
                      fontSize: 11,
                      fill: "var(--chakra-colors-fg-muted)",
                    }}
                  />
                  <YAxis
                    tick={{
                      fontSize: 11,
                      fill: "var(--chakra-colors-fg-muted)",
                    }}
                  />
                  <Tooltip />
                  <Legend />
                  <Line
                    dataKey="Auth Success"
                    type="monotone"
                    stroke="var(--chakra-colors-green-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Auth Fail"
                    type="monotone"
                    stroke="var(--chakra-colors-red-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Authz Permit"
                    type="monotone"
                    stroke="var(--chakra-colors-blue-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Authz Deny"
                    type="monotone"
                    stroke="var(--chakra-colors-orange-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Acct Start"
                    type="monotone"
                    stroke="var(--chakra-colors-purple-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Acct Stop"
                    type="monotone"
                    stroke="var(--chakra-colors-gray-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </Box>
          </GridItem>
        </Grid>
      )}
    </Box>
  )
}

function RangeStatsTab() {
  const [startDate, setStartDate] = useState<string>(
    getISODateString(sevenDaysAgo),
  )
  const [endDate, setEndDate] = useState<string>(getISODateString(yesterday))
  const [selectedNode, setSelectedNode] = useState<string>("")

  const { data: nodes } = useQuery({
    queryKey: ["aaa_nodes"],
    queryFn: () => AaaStatisticsService.listAaaNodes(),
  })

  const {
    data: stats,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["aaa_statistics_range", startDate, endDate, selectedNode],
    queryFn: () =>
      AaaStatisticsService.readAaaStatisticsRange({
        rangeDate: `${startDate},${endDate}`,
        nodeName: selectedNode || undefined,
      }),
    refetchInterval: 5 * 60 * 1000, // refresh every 5 minutes
  })

  const data_authentication_success_count_by_user =
    stats?.authentication_success_count_by_user?.map((user: any, index) => ({
      name: (user.username as string) || "",
      value: (user.success_count as number) || 0,
      color: CHART_COLORS[index % CHART_COLORS.length],
    })) || []

  const data_authentication_success_count_by_user_source_ip =
    stats?.authentication_success_count_by_user_source_ip?.map(
      (user: any, index) => ({
        name: (user.user_source_ip as string) || "",
        value: (user.success_count as number) || 0,
        color: CHART_COLORS[index % CHART_COLORS.length],
      }),
    ) || []

  const data_authentication_success_count_by_nas_ip =
    stats?.authentication_success_count_by_nas_ip?.map((user: any, index) => ({
      name: (user.nas_ip as string) || "",
      value: (user.success_count as number) || 0,
      color: CHART_COLORS[index % CHART_COLORS.length],
    })) || []

  const data_authentication_failed_count_by_user =
    stats?.authentication_failed_count_by_user?.map((user: any, index) => ({
      name: (user.username as string) || "",
      value: (user.fail_count as number) || 0,
      color: FAIL_COLORS[index % FAIL_COLORS.length],
    })) || []

  const last_range_days_data =
    stats?.last_range_days_authentication_success?.map((item, index) => ({
      date: new Date(item.date as string).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      "Auth Success": item.count,
      "Auth Fail":
        stats?.last_range_days_authentication_fail?.[index]?.count || 0,
      "Authz Permit":
        stats?.last_range_days_authorization_permit?.[index]?.count || 0,
      "Authz Deny":
        stats?.last_range_days_authorization_deny?.[index]?.count || 0,
      "Acct Start":
        stats?.last_range_days_accounting_start?.[index]?.count || 0,
      "Acct Stop": stats?.last_range_days_accounting_stop?.[index]?.count || 0,
    })) || []

  // Range-wide totals calculations
  const totalSuccess =
    stats?.last_range_days_authentication_success?.reduce(
      (acc: number, item: any) => acc + (item.count || 0),
      0,
    ) || 0
  const totalFail =
    stats?.last_range_days_authentication_fail?.reduce(
      (acc: number, item: any) => acc + (item.count || 0),
      0,
    ) || 0
  const totalPermit =
    stats?.last_range_days_authorization_permit?.reduce(
      (acc: number, item: any) => acc + (item.count || 0),
      0,
    ) || 0
  const totalDeny =
    stats?.last_range_days_authorization_deny?.reduce(
      (acc: number, item: any) => acc + (item.count || 0),
      0,
    ) || 0

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6} gap={4} wrap="wrap">
        <Heading size="md" fontWeight="bold">
          Historic Activity Range
        </Heading>
        <Flex align="center" gap={3} wrap="wrap">
          <NativeSelect.Root size="sm" width="140px">
            <NativeSelect.Field
              value={selectedNode}
              onChange={(e) => setSelectedNode(e.target.value)}
            >
              <option value="">All Nodes</option>
              {(nodes ?? []).map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
          <Flex align="center" gap={2}>
            <Text fontSize="sm" color="fg.muted" whiteSpace="nowrap">
              From
            </Text>
            <Input
              size="sm"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              maxW="150px"
              borderRadius="md"
            />
          </Flex>
          <Flex align="center" gap={2}>
            <Text fontSize="sm" color="fg.muted" whiteSpace="nowrap">
              To
            </Text>
            <Input
              size="sm"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              maxW="150px"
              borderRadius="md"
              min={startDate}
              max={getISODateString(yesterday)}
            />
          </Flex>
        </Flex>
      </Flex>

      {isLoading ? (
        <Flex justify="center" align="center" height="40vh">
          <Spinner size="xl" />
        </Flex>
      ) : error ? (
        <Box p={4} borderWidth="1px" borderRadius="lg" borderColor="red.200">
          <Text color="red.500">
            Error fetching statistics: {error.message}
          </Text>
        </Box>
      ) : (
        <Grid
          templateColumns={{
            base: "1fr",
            md: "repeat(2, 1fr)",
            xl: "repeat(4, 1fr)",
          }}
          gap={6}
        >
          {/* Summary Cards */}
          <GridItem colSpan={1}>
            <StatCard
              label="Range Auth Success"
              value={totalSuccess}
              highlight="success"
            />
          </GridItem>
          <GridItem colSpan={1}>
            <StatCard
              label="Range Auth Fail"
              value={totalFail}
              highlight="danger"
            />
          </GridItem>
          <GridItem colSpan={1}>
            <StatCard
              label="Range Authz Permit"
              value={totalPermit}
              highlight="info"
            />
          </GridItem>
          <GridItem colSpan={1}>
            <StatCard
              label="Range Authz Deny"
              value={totalDeny}
              highlight="warning"
            />
          </GridItem>

          {/* Top 5 Charts */}
          <GridItem colSpan={{ base: 1, md: 2, xl: 1 }}>
            <StatPie
              title="Top 5 Users Login Success"
              data={data_authentication_success_count_by_user}
            />
          </GridItem>
          <GridItem colSpan={{ base: 1, md: 2, xl: 1 }}>
            <StatPie
              title="Top 5 Source IPs"
              data={data_authentication_success_count_by_user_source_ip}
            />
          </GridItem>
          <GridItem colSpan={{ base: 1, md: 2, xl: 1 }}>
            <StatPie
              title="Top 5 NAS IPs"
              data={data_authentication_success_count_by_nas_ip}
            />
          </GridItem>
          <GridItem colSpan={{ base: 1, md: 2, xl: 1 }}>
            <StatPie
              title="Top 5 Users Login Failed"
              data={data_authentication_failed_count_by_user}
            />
          </GridItem>

          {/* Trend Chart */}
          <GridItem colSpan={{ base: 1, md: 2, xl: 4 }}>
            <Box
              p={5}
              bg="bg.panel"
              borderWidth="1px"
              borderRadius="xl"
              shadow="sm"
              transition="all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
              _hover={{
                borderColor: "teal.500",
                shadow: "md",
                transform: "translateY(-4px)",
              }}
              h="100%"
            >
              <Heading size="sm" mb={4} fontWeight="bold">
                AAA Statistics From {startDate} to {endDate}
              </Heading>
              <ResponsiveContainer width="100%" height={350}>
                <LineChart
                  data={last_range_days_data}
                  margin={{ top: 10, right: 30, left: -20, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--chakra-colors-border)"
                  />
                  <XAxis
                    dataKey="date"
                    tick={{
                      fontSize: 11,
                      fill: "var(--chakra-colors-fg-muted)",
                    }}
                  />
                  <YAxis
                    tick={{
                      fontSize: 11,
                      fill: "var(--chakra-colors-fg-muted)",
                    }}
                  />
                  <Tooltip />
                  <Legend />
                  <Line
                    dataKey="Auth Success"
                    type="monotone"
                    stroke="var(--chakra-colors-green-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Auth Fail"
                    type="monotone"
                    stroke="var(--chakra-colors-red-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Authz Permit"
                    type="monotone"
                    stroke="var(--chakra-colors-blue-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Authz Deny"
                    type="monotone"
                    stroke="var(--chakra-colors-orange-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Acct Start"
                    type="monotone"
                    stroke="var(--chakra-colors-purple-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    dataKey="Acct Stop"
                    type="monotone"
                    stroke="var(--chakra-colors-gray-500)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </Box>
          </GridItem>
        </Grid>
      )}
    </Box>
  )
}

interface NodeCardProps {
  nodeName: string
  startDate: string
  endDate: string
  accentColor: string
}

function NodeCard({
  nodeName,
  startDate,
  endDate,
  accentColor,
}: NodeCardProps) {
  const { data: stats, isLoading } = useQuery<AaaStatisticsDateRangePublic>({
    queryKey: ["aaa_node_stats", nodeName, startDate, endDate],
    queryFn: () =>
      AaaStatisticsService.readAaaStatisticsRange({
        rangeDate: `${startDate},${endDate}`,
        nodeName,
      }),
    refetchInterval: 5 * 60 * 1000, // refresh every 5 minutes
  })

  const trendData =
    stats?.last_range_days_authentication_success?.map((item, index) => ({
      date: new Date(item.date as string).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      "Auth Success": item.count ?? 0,
      "Auth Fail":
        stats?.last_range_days_authentication_fail?.[index]?.count ?? 0,
      "Authz Permit":
        stats?.last_range_days_authorization_permit?.[index]?.count ?? 0,
      "Authz Deny":
        stats?.last_range_days_authorization_deny?.[index]?.count ?? 0,
    })) ?? []

  const totalSuccess = sumField(stats?.last_range_days_authentication_success)
  const totalFail = sumField(stats?.last_range_days_authentication_fail)
  const totalPermit = sumField(stats?.last_range_days_authorization_permit)
  const totalDeny = sumField(stats?.last_range_days_authorization_deny)
  const totalAcctStart = sumField(stats?.last_range_days_accounting_start)
  const totalAcctStop = sumField(stats?.last_range_days_accounting_stop)

  const colorPalette = accentColor.split(".")[0]

  return (
    <Box
      bg="bg.panel"
      borderWidth="1px"
      borderLeftWidth="4px"
      borderLeftColor={accentColor}
      borderRadius="xl"
      shadow="sm"
      transition="all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
      _hover={{
        shadow: "md",
        borderColor: accentColor,
        transform: "translateY(-4px)",
      }}
      overflow="hidden"
      h="100%"
    >
      <Flex
        align="center"
        justify="space-between"
        px={5}
        py={4}
        borderBottomWidth="1px"
        borderColor="border.subtle"
      >
        <Flex align="center" gap={2}>
          <Box
            p={1.5}
            bg={`${colorPalette}.muted`}
            color={`${colorPalette}.fg`}
            borderRadius="md"
          >
            <FiServer fontSize="16px" />
          </Box>
          <Heading size="sm" fontWeight="bold">
            {nodeName}
          </Heading>
        </Flex>
        <Badge
          colorPalette={colorPalette}
          variant="subtle"
          size="sm"
          borderRadius="md"
        >
          node
        </Badge>
      </Flex>

      {isLoading ? (
        <Flex justify="center" align="center" h="350px">
          <Spinner color={accentColor} size="lg" />
        </Flex>
      ) : (
        <Box p={5}>
          {/* Metrics Grid */}
          <Grid templateColumns="repeat(2, 1fr)" gap={3} mb={5}>
            <Box p={3} bg="bg.muted" borderRadius="lg" borderWidth="1px">
              <Stat.Root size="sm">
                <Stat.Label fontSize="xs" fontWeight="medium" color="fg.muted">
                  Auth Success
                </Stat.Label>
                <Stat.ValueText
                  fontSize="xl"
                  fontWeight="bold"
                  color="green.500"
                  fontFamily="mono"
                >
                  {totalSuccess}
                </Stat.ValueText>
              </Stat.Root>
            </Box>
            <Box p={3} bg="bg.muted" borderRadius="lg" borderWidth="1px">
              <Stat.Root size="sm">
                <Stat.Label fontSize="xs" fontWeight="medium" color="fg.muted">
                  Auth Fail
                </Stat.Label>
                <Stat.ValueText
                  fontSize="xl"
                  fontWeight="bold"
                  color={totalFail > 0 ? "red.500" : "fg.subtle"}
                  fontFamily="mono"
                >
                  {totalFail}
                </Stat.ValueText>
              </Stat.Root>
            </Box>
            <Box p={3} bg="bg.muted" borderRadius="lg" borderWidth="1px">
              <Stat.Root size="sm">
                <Stat.Label fontSize="xs" fontWeight="medium" color="fg.muted">
                  Authz Permit
                </Stat.Label>
                <Stat.ValueText
                  fontSize="xl"
                  fontWeight="bold"
                  color="blue.500"
                  fontFamily="mono"
                >
                  {totalPermit}
                </Stat.ValueText>
              </Stat.Root>
            </Box>
            <Box p={3} bg="bg.muted" borderRadius="lg" borderWidth="1px">
              <Stat.Root size="sm">
                <Stat.Label fontSize="xs" fontWeight="medium" color="fg.muted">
                  Authz Deny
                </Stat.Label>
                <Stat.ValueText
                  fontSize="xl"
                  fontWeight="bold"
                  color={totalDeny > 0 ? "orange.500" : "fg.subtle"}
                  fontFamily="mono"
                >
                  {totalDeny}
                </Stat.ValueText>
              </Stat.Root>
            </Box>
            <Box p={3} bg="bg.muted" borderRadius="lg" borderWidth="1px">
              <Stat.Root size="sm">
                <Stat.Label fontSize="xs" fontWeight="medium" color="fg.muted">
                  Acct Start
                </Stat.Label>
                <Stat.ValueText
                  fontSize="xl"
                  fontWeight="bold"
                  color="purple.500"
                  fontFamily="mono"
                >
                  {totalAcctStart}
                </Stat.ValueText>
              </Stat.Root>
            </Box>
            <Box p={3} bg="bg.muted" borderRadius="lg" borderWidth="1px">
              <Stat.Root size="sm">
                <Stat.Label fontSize="xs" fontWeight="medium" color="fg.muted">
                  Acct Stop
                </Stat.Label>
                <Stat.ValueText
                  fontSize="xl"
                  fontWeight="bold"
                  color="gray.500"
                  fontFamily="mono"
                >
                  {totalAcctStop}
                </Stat.ValueText>
              </Stat.Root>
            </Box>
          </Grid>

          {/* Trend Chart */}
          <Box p={3} borderWidth="1px" borderRadius="lg" bg="bg.panel" mb={5}>
            <Text
              fontSize="xs"
              fontWeight="bold"
              textTransform="uppercase"
              letterSpacing="wider"
              color="fg.muted"
              mb={3}
            >
              Activity Trend
            </Text>
            {trendData.length === 0 ? (
              <Flex
                direction="column"
                align="center"
                justify="center"
                h="150px"
                gap={2}
              >
                <Box p={2} bg="bg.muted" borderRadius="full" color="fg.subtle">
                  <FiInbox fontSize="18px" />
                </Box>
                <Text fontSize="xs" color="fg.subtle">
                  No trend data available
                </Text>
              </Flex>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart
                  data={trendData}
                  margin={{ top: 4, right: 8, left: -25, bottom: 0 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="var(--chakra-colors-border)"
                  />
                  <XAxis
                    dataKey="date"
                    tick={{
                      fontSize: 9,
                      fill: "var(--chakra-colors-fg-muted)",
                    }}
                  />
                  <YAxis
                    tick={{
                      fontSize: 9,
                      fill: "var(--chakra-colors-fg-muted)",
                    }}
                  />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 9, marginTop: 8 }} />
                  <Line
                    dataKey="Auth Success"
                    type="monotone"
                    stroke="var(--chakra-colors-green-500)"
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={{ r: 3 }}
                  />
                  <Line
                    dataKey="Auth Fail"
                    type="monotone"
                    stroke="var(--chakra-colors-red-500)"
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={{ r: 3 }}
                  />
                  <Line
                    dataKey="Authz Permit"
                    type="monotone"
                    stroke="var(--chakra-colors-blue-500)"
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={{ r: 3 }}
                  />
                  <Line
                    dataKey="Authz Deny"
                    type="monotone"
                    stroke="var(--chakra-colors-orange-500)"
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Box>

          {/* Top Users Lists */}
          <Grid templateColumns="repeat(2, 1fr)" gap={3}>
            {/* Top Users Success */}
            <Box p={3} borderWidth="1px" borderRadius="lg" bg="bg.panel">
              <Text
                fontSize="xs"
                fontWeight="bold"
                textTransform="uppercase"
                letterSpacing="wider"
                color="fg.muted"
                mb={2}
              >
                Top Users (Success)
              </Text>
              {(stats?.authentication_success_count_by_user ?? []).length ===
              0 ? (
                <Flex align="center" justify="center" h="60px">
                  <Text fontSize="xs" color="fg.subtle" fontStyle="italic">
                    None
                  </Text>
                </Flex>
              ) : (
                (
                  stats?.authentication_success_count_by_user as Array<{
                    username: string
                    success_count: number
                  }>
                )
                  ?.slice(0, 3)
                  .map((u) => (
                    <Flex
                      key={u.username}
                      justify="space-between"
                      align="center"
                      py={1.5}
                      borderBottomWidth="1px"
                      borderColor="border.subtle"
                      _last={{ borderBottomWidth: 0 }}
                    >
                      <Text
                        truncate
                        maxW="70px"
                        fontSize="xs"
                        fontWeight="medium"
                      >
                        {u.username}
                      </Text>
                      <Text
                        color="green.500"
                        fontSize="xs"
                        fontWeight="bold"
                        fontFamily="mono"
                      >
                        {u.success_count}
                      </Text>
                    </Flex>
                  ))
              )}
            </Box>

            {/* Top Users Failed */}
            <Box p={3} borderWidth="1px" borderRadius="lg" bg="bg.panel">
              <Text
                fontSize="xs"
                fontWeight="bold"
                textTransform="uppercase"
                letterSpacing="wider"
                color="fg.muted"
                mb={2}
              >
                Top Users (Failed)
              </Text>
              {(stats?.authentication_failed_count_by_user ?? []).length ===
              0 ? (
                <Flex align="center" justify="center" h="60px">
                  <Text fontSize="xs" color="fg.subtle" fontStyle="italic">
                    None
                  </Text>
                </Flex>
              ) : (
                (
                  stats?.authentication_failed_count_by_user as Array<{
                    username: string
                    fail_count: number
                  }>
                )
                  ?.slice(0, 3)
                  .map((u) => (
                    <Flex
                      key={u.username}
                      justify="space-between"
                      align="center"
                      py={1.5}
                      borderBottomWidth="1px"
                      borderColor="border.subtle"
                      _last={{ borderBottomWidth: 0 }}
                    >
                      <Text
                        truncate
                        maxW="70px"
                        fontSize="xs"
                        fontWeight="medium"
                      >
                        {u.username}
                      </Text>
                      <Text
                        color="red.500"
                        fontSize="xs"
                        fontWeight="bold"
                        fontFamily="mono"
                      >
                        {u.fail_count}
                      </Text>
                    </Flex>
                  ))
              )}
            </Box>
          </Grid>
        </Box>
      )}
    </Box>
  )
}

function NodeStatsTab() {
  const [startDate, setStartDate] = useState<string>(
    getISODateString(sevenDaysAgo),
  )
  const [endDate, setEndDate] = useState<string>(getISODateString(yesterday))

  const { data: nodes, isLoading: nodesLoading } = useQuery({
    queryKey: ["aaa_nodes"],
    queryFn: () => AaaStatisticsService.listAaaNodes(),
  })

  const nodeList = nodes ?? []

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6} gap={4} wrap="wrap">
        <Heading size="md" fontWeight="bold">
          Node Comparison
        </Heading>
        <Flex align="center" gap={3} wrap="wrap">
          <Flex align="center" gap={2}>
            <Text
              fontSize="sm"
              fontWeight="medium"
              color="fg.muted"
              whiteSpace="nowrap"
            >
              From
            </Text>
            <Input
              size="sm"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              maxW="150px"
              borderRadius="md"
            />
          </Flex>
          <Flex align="center" gap={2}>
            <Text
              fontSize="sm"
              fontWeight="medium"
              color="fg.muted"
              whiteSpace="nowrap"
            >
              To
            </Text>
            <Input
              size="sm"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              maxW="150px"
              borderRadius="md"
              min={startDate}
              max={getISODateString(yesterday)}
            />
          </Flex>
        </Flex>
      </Flex>

      {nodesLoading ? (
        <Flex justify="center" align="center" height="40vh">
          <Spinner size="xl" />
        </Flex>
      ) : nodeList.length === 0 ? (
        <Box
          p={8}
          textAlign="center"
          borderWidth="1px"
          borderRadius="xl"
          bg="bg.panel"
          shadow="sm"
        >
          <Flex direction="column" align="center" justify="center" gap={3}>
            <Box p={4} bg="bg.muted" borderRadius="full" color="fg.subtle">
              <FiServer fontSize="32px" />
            </Box>
            <Text color="fg.muted" fontWeight="bold">
              No Node Statistics Found
            </Text>
            <Text color="fg.subtle" fontSize="sm">
              Please run statistics collection first or check if nodes are
              active.
            </Text>
          </Flex>
        </Box>
      ) : (
        <Grid
          templateColumns={{
            base: "1fr",
            md: `repeat(${Math.min(nodeList.length, 2)}, 1fr)`,
            xl: `repeat(${Math.min(nodeList.length, 3)}, 1fr)`,
          }}
          gap={6}
          alignItems="start"
        >
          {nodeList.map((nodeName, index) => (
            <GridItem key={nodeName}>
              <NodeCard
                nodeName={nodeName}
                startDate={startDate}
                endDate={endDate}
                accentColor={NODE_COLORS[index % NODE_COLORS.length]}
              />
            </GridItem>
          ))}
        </Grid>
      )}
    </Box>
  )
}

// ─── Main Component ──────────────────────────────────────────────────────

export function AaaStatistics() {
  return (
    <Container maxW="full" py={8}>
      <PageHeader
        title="AAA Statistics Dashboard"
        description="Monitor, analyze, and compare TACACS+ authentication, authorization, and accounting events."
        icon={FiBarChart2}
      />
      <Tabs.Root defaultValue="today" mt={6} variant="subtle">
        <Tabs.List>
          <Tabs.Trigger value="today">
            <FiActivity style={{ marginRight: "6px" }} />
            Today
          </Tabs.Trigger>
          <Tabs.Trigger value="range">
            <FiCalendar style={{ marginRight: "6px" }} />
            Historic Range
          </Tabs.Trigger>
          <Tabs.Trigger value="nodes">
            <FiServer style={{ marginRight: "6px" }} />
            Node Comparison
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="today" pt={5}>
          <TodayStatsTab />
        </Tabs.Content>

        <Tabs.Content value="range" pt={5}>
          <RangeStatsTab />
        </Tabs.Content>

        <Tabs.Content value="nodes" pt={5}>
          <NodeStatsTab />
        </Tabs.Content>
      </Tabs.Root>
    </Container>
  )
}
