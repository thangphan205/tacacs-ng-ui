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

interface NodeCardProps {
  nodeName: string
  startDate: string
  endDate: string
}

function NodeCard({ nodeName, startDate, endDate }: NodeCardProps) {
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

  return (
    <Box borderWidth="1px" borderRadius="lg" overflow="hidden" h="100%">
      <Flex
        align="center"
        gap={2}
        px={4}
        py={3}
        borderBottomWidth="1px"
        bg="bg.subtle"
      >
        <Heading size="sm">{nodeName}</Heading>
        <Badge colorPalette="blue" size="sm">
          node
        </Badge>
      </Flex>

      {isLoading ? (
        <Flex justify="center" align="center" h="200px">
          <Spinner />
        </Flex>
      ) : (
        <Box p={4}>
          <Grid templateColumns="repeat(2, 1fr)" gap={3} mb={4}>
            <GridItem>
              <Stat.Root size="sm">
                <Stat.Label>Auth Success</Stat.Label>
                <Stat.ValueText color="green.500">{totalSuccess}</Stat.ValueText>
              </Stat.Root>
            </GridItem>
            <GridItem>
              <Stat.Root size="sm">
                <Stat.Label>Auth Fail</Stat.Label>
                <Stat.ValueText color={totalFail > 0 ? "red.500" : undefined}>
                  {totalFail}
                </Stat.ValueText>
              </Stat.Root>
            </GridItem>
            <GridItem>
              <Stat.Root size="sm">
                <Stat.Label>Authz Permit</Stat.Label>
                <Stat.ValueText color="blue.500">{totalPermit}</Stat.ValueText>
              </Stat.Root>
            </GridItem>
            <GridItem>
              <Stat.Root size="sm">
                <Stat.Label>Authz Deny</Stat.Label>
                <Stat.ValueText color={totalDeny > 0 ? "orange.500" : undefined}>
                  {totalDeny}
                </Stat.ValueText>
              </Stat.Root>
            </GridItem>
            <GridItem>
              <Stat.Root size="sm">
                <Stat.Label>Acct Start</Stat.Label>
                <Stat.ValueText>{totalAcctStart}</Stat.ValueText>
              </Stat.Root>
            </GridItem>
            <GridItem>
              <Stat.Root size="sm">
                <Stat.Label>Acct Stop</Stat.Label>
                <Stat.ValueText>{totalAcctStop}</Stat.ValueText>
              </Stat.Root>
            </GridItem>
          </Grid>

          <Box mt={2}>
            <Text fontSize="xs" color="fg.subtle" mb={2}>
              Trend
            </Text>
            <Chart.Root chart={chart} height="180px">
              <AreaChart
                data={trendData}
                margin={{ top: 4, right: 8, left: -20, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Area
                  dataKey="Auth Success"
                  type="monotone"
                  fill="var(--chakra-colors-green-500)"
                  stroke="var(--chakra-colors-green-600)"
                  fillOpacity={0.4}
                />
                <Area
                  dataKey="Auth Fail"
                  type="monotone"
                  fill="var(--chakra-colors-red-500)"
                  stroke="var(--chakra-colors-red-600)"
                  fillOpacity={0.4}
                />
                <Area
                  dataKey="Authz Permit"
                  type="monotone"
                  fill="var(--chakra-colors-blue-500)"
                  stroke="var(--chakra-colors-blue-600)"
                  fillOpacity={0.4}
                />
                <Area
                  dataKey="Authz Deny"
                  type="monotone"
                  fill="var(--chakra-colors-orange-500)"
                  stroke="var(--chakra-colors-orange-600)"
                  fillOpacity={0.4}
                />
              </AreaChart>
            </Chart.Root>
          </Box>

          {(stats?.authentication_success_count_by_user ?? []).length > 0 && (
            <Box mt={3}>
              <Text fontSize="xs" color="fg.subtle" mb={1}>
                Top Users (success)
              </Text>
              {(stats?.authentication_success_count_by_user as Array<{username: string; success_count: number}>)
                ?.slice(0, 3)
                .map((u) => (
                  <Flex key={u.username} justify="space-between" fontSize="xs">
                    <Text truncate maxW="120px">
                      {u.username}
                    </Text>
                    <Text color="green.500">{u.success_count}</Text>
                  </Flex>
                ))}
            </Box>
          )}

          {(stats?.authentication_failed_count_by_user ?? []).length > 0 && (
            <Box mt={3}>
              <Text fontSize="xs" color="fg.subtle" mb={1}>
                Top Users (failed)
              </Text>
              {(stats?.authentication_failed_count_by_user as Array<{username: string; fail_count: number}>)
                ?.slice(0, 3)
                .map((u) => (
                  <Flex key={u.username} justify="space-between" fontSize="xs">
                    <Text truncate maxW="120px">
                      {u.username}
                    </Text>
                    <Text color="red.500">{u.fail_count}</Text>
                  </Flex>
                ))}
            </Box>
          )}
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
      <Flex justify="space-between" align="center" mb={6} gap={4} wrap="wrap">
        <Heading size="md">TACACS+ Node Comparison</Heading>
        <Flex gap={4} align="center">
          <Text fontSize="sm">From</Text>
          <Input
            size="sm"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            maxW="160px"
          />
          <Text fontSize="sm">To</Text>
          <Input
            size="sm"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            maxW="160px"
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
        <Box p={8} textAlign="center" borderWidth="1px" borderRadius="lg">
          <Text color="fg.subtle">
            No node statistics found. Run statistics collection first.
          </Text>
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
          {nodeList.map((nodeName) => (
            <GridItem key={nodeName}>
              <NodeCard
                nodeName={nodeName}
                startDate={startDate}
                endDate={endDate}
              />
            </GridItem>
          ))}
        </Grid>
      )}
    </Container>
  )
}
