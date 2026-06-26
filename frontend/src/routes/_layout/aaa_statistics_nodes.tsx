import { Chart, useChart } from "@chakra-ui/charts"
import {
  Badge,
  Box,
  Container,
  Flex,
  Grid,
  GridItem,
  Heading,
  Input,
  Spinner,
  Stat,
  Text,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { FiInbox, FiServer } from "react-icons/fi"
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import type { AaaStatisticsDateRangePublic } from "@/client"
import { AaaStatisticsService } from "@/client"
import PageHeader from "@/components/Common/PageHeader"

const getISODateString = (date: Date): string =>
  date.toISOString().split("T")[0]

const today = new Date()
const yesterday = new Date(today)
yesterday.setDate(yesterday.getDate() - 1)
const sevenDaysAgo = new Date(today)
sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)

export const Route = createFileRoute("/_layout/aaa_statistics_nodes")({
  component: AaaStatisticsNodes,
})

function sumField(list: { count?: number }[] | undefined): number {
  return (list ?? []).reduce((s, d) => s + (d.count ?? 0), 0)
}

const NODE_COLORS = [
  "teal.500",
  "blue.500",
  "purple.500",
  "pink.500",
  "orange.500",
]

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

  const chart = useChart({
    data: trendData,
    series: [
      { name: "Auth Success", color: "green.500" },
      { name: "Auth Fail", color: "red.500" },
      { name: "Authz Permit", color: "blue.500" },
      { name: "Authz Deny", color: "orange.500" },
    ],
  })

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
              <Chart.Root chart={chart} height="180px">
                <AreaChart
                  data={trendData}
                  margin={{ top: 4, right: 8, left: -25, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} />
                  <YAxis tick={{ fontSize: 9 }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 9, marginTop: 8 }} />
                  <Area
                    dataKey="Auth Success"
                    type="monotone"
                    fill="var(--chakra-colors-green-500)"
                    stroke="var(--chakra-colors-green-600)"
                    fillOpacity={0.15}
                  />
                  <Area
                    dataKey="Auth Fail"
                    type="monotone"
                    fill="var(--chakra-colors-red-500)"
                    stroke="var(--chakra-colors-red-600)"
                    fillOpacity={0.15}
                  />
                  <Area
                    dataKey="Authz Permit"
                    type="monotone"
                    fill="var(--chakra-colors-blue-500)"
                    stroke="var(--chakra-colors-blue-600)"
                    fillOpacity={0.15}
                  />
                  <Area
                    dataKey="Authz Deny"
                    type="monotone"
                    fill="var(--chakra-colors-orange-500)"
                    stroke="var(--chakra-colors-orange-600)"
                    fillOpacity={0.15}
                  />
                </AreaChart>
              </Chart.Root>
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

export function AaaStatisticsNodes() {
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
    <Container maxW="full" py={8}>
      <Flex
        justify="space-between"
        align="flex-start"
        mb={6}
        gap={4}
        wrap="wrap"
      >
        <PageHeader
          title="TACACS+ Node Comparison"
          description="Compare AAA statistics and active event trends across different primary and standby nodes."
          icon={FiServer}
        />
        <Flex align="center" gap={3} pt={{ base: 0, md: 6 }} wrap="wrap">
          <Text fontSize="sm" fontWeight="medium" color="fg.muted">
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
          <Text fontSize="sm" fontWeight="medium" color="fg.muted">
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

      {nodesLoading ? (
        <Flex justify="center" align="center" height="50vh">
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
    </Container>
  )
}
