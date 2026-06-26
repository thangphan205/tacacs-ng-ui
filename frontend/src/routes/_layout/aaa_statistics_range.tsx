import { Chart, useChart } from "@chakra-ui/charts"
import {
  Box,
  Container,
  Flex,
  Grid,
  GridItem,
  Heading,
  Input,
  NativeSelect,
  Spinner,
  Stat,
  Text,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import {
  FiActivity,
  FiCalendar,
  FiGlobe,
  FiInbox,
  FiServer,
  FiShield,
  FiShieldOff,
} from "react-icons/fi"
import {
  Area,
  AreaChart,
  CartesianGrid,
  LabelList,
  Legend,
  Pie,
  PieChart,
  Sector,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { AaaStatisticsService } from "@/client"
import PageHeader from "@/components/Common/PageHeader"

const getISODateString = (date: Date): string =>
  date.toISOString().split("T")[0]

const today = new Date()
const yesterday = new Date(today)
yesterday.setDate(yesterday.getDate() - 1)
const sevenDaysAgo = new Date(today)
sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)

export const Route = createFileRoute("/_layout/aaa_statistics_range")({
  component: AaaStatisticsRange,
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

// ─── Interfaces & Sub-components ─────────────────────────────────────────

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
            No records for selected range
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

// ─── Main Component ──────────────────────────────────────────────────────

export function AaaStatisticsRange() {
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

  const handleStartDateChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    setStartDate(event.target.value)
  }

  const handleEndDateChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEndDate(event.target.value)
  }

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

  const chart_last_range_days = useChart({
    data: last_range_days_data,
    series: [
      { name: "Auth Success", color: "green.500" },
      { name: "Auth Fail", color: "red.500" },
      { name: "Authz Permit", color: "blue.500" },
      { name: "Authz Deny", color: "orange.500" },
      { name: "Acct Start", color: "purple.500" },
      { name: "Acct Stop", color: "gray.500" },
    ],
  })

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
    <Container maxW="full" py={8}>
      <Flex
        justify="space-between"
        align="flex-start"
        mb={6}
        gap={4}
        wrap="wrap"
      >
        <PageHeader
          title="Historic AAA Statistics"
          description={`Analyze TACACS+ authentication, authorization, and accounting trends across custom date ranges.`}
          icon={FiCalendar}
        />
        <Flex align="center" gap={3} pt={{ base: 0, md: 6 }} wrap="wrap">
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
          <Text fontSize="sm" color="fg.muted">
            From
          </Text>
          <Input
            size="sm"
            type="date"
            value={startDate}
            onChange={handleStartDateChange}
            maxW="150px"
          />
          <Text fontSize="sm" color="fg.muted">
            To
          </Text>
          <Input
            size="sm"
            type="date"
            value={endDate}
            onChange={handleEndDateChange}
            maxW="150px"
            min={startDate}
            max={getISODateString(yesterday)}
          />
        </Flex>
      </Flex>

      {isLoading ? (
        <Flex justify="center" align="center" height="50vh">
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
              <Chart.Root chart={chart_last_range_days} height="350px">
                <AreaChart
                  width={800}
                  height={350}
                  data={last_range_days_data}
                  margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <Tooltip />
                  <Legend />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Area
                    dataKey="Auth Success"
                    type="monotone"
                    fill="var(--chakra-colors-green-500)"
                    stroke="var(--chakra-colors-green-600)"
                  />
                  <Area
                    dataKey="Auth Fail"
                    type="monotone"
                    fill="var(--chakra-colors-red-500)"
                    stroke="var(--chakra-colors-red-600)"
                  />
                  <Area
                    dataKey="Authz Permit"
                    type="monotone"
                    fill="var(--chakra-colors-blue-500)"
                    stroke="var(--chakra-colors-blue-600)"
                  />
                  <Area
                    dataKey="Authz Deny"
                    type="monotone"
                    fill="var(--chakra-colors-orange-500)"
                    stroke="var(--chakra-colors-orange-600)"
                  />
                  <Area
                    dataKey="Acct Start"
                    type="monotone"
                    fill="var(--chakra-colors-purple-500)"
                    stroke="var(--chakra-colors-purple-600)"
                  />
                  <Area
                    dataKey="Acct Stop"
                    type="monotone"
                    fill="var(--chakra-colors-gray-500)"
                    stroke="var(--chakra-colors-gray-600)"
                  />
                </AreaChart>
              </Chart.Root>
            </Box>
          </GridItem>
        </Grid>
      )}
    </Container>
  )
}
