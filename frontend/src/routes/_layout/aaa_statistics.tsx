import {
  Box,
  Container,
  Flex,
  Grid,
  GridItem,
  Heading,
  Spinner,
  Stat,
  Text,
} from "@chakra-ui/react"
import { Chart, useChart } from "@chakra-ui/charts"
import { Area, AreaChart, CartesianGrid, Cell, LabelList, Legend, Pie, PieChart, Tooltip, XAxis, YAxis } from "recharts"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import {
  AaaStatisticsService,
} from "@/client"


export const Route = createFileRoute("/_layout/aaa_statistics")({
  component: AaaStatistics,
})

export function AaaStatistics() {

  const {
    data: stats,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["aaa_statistics"],
    queryFn: () =>
      AaaStatisticsService.readAaaStatistics(),
  })


  const color_chart = ["blue.500", "green.500", "pink.500", "orange.500", "red.500"]
  const data_authentication_success_count_by_user = stats?.today_authentication_success_count_by_user?.map((user, index) => ({
    name: user.username,
    value: user.success_count,
    color: color_chart[index]
  })) || [];
  const chart_authentication_success_count_by_user = useChart({
    data: data_authentication_success_count_by_user
  })
  const data_authentication_success_count_by_user_source_ip = stats?.today_authentication_success_count_by_user_source_ip?.map((user, index) => ({
    name: user.user_source_ip,
    value: user.success_count,
    color: color_chart[index]
  })) || [];
  const chart_authentication_success_count_by_user_source_ip = useChart({
    data: data_authentication_success_count_by_user_source_ip
  })

  const data_authentication_success_count_by_nas_ip = stats?.today_authentication_success_count_by_nas_ip?.map((user, index) => ({
    name: user.nas_ip,
    value: user.success_count,
    color: color_chart[index]
  })) || [];
  const chart_authentication_success_count_by_nas_ip = useChart({
    data: data_authentication_success_count_by_nas_ip
  })

  const color_chart_failed = ["red.500", "orange.500", "pink.500", "green.500", "blue.500"]
  const data_authentication_failed_count_by_user = stats?.today_authentication_failed_count_by_user?.map((user, index) => ({
    name: user.username,
    value: user.fail_count,
    color: color_chart_failed[index]
  })) || [];
  const chart_authentication_failed_count_by_user = useChart({
    data: data_authentication_failed_count_by_user,
  })

  const last_7_days_data = stats?.last_7_days_authentication_success?.map((item, index) => ({
    date: new Date(item.date as string).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    'Auth Success': item.count,
    'Auth Fail': stats?.last_7_days_authentication_fail?.[index]?.count || 0,
    'Authz Permit': stats?.last_7_days_authorization_permit?.[index]?.count || 0,
    'Authz Deny': stats?.last_7_days_authorization_deny?.[index]?.count || 0,
    'Acct Start': stats?.last_7_days_accounting_start?.[index]?.count || 0,
    'Acct Stop': stats?.last_7_days_accounting_stop?.[index]?.count || 0,
  })) || [];

  const chart_last_7_days = useChart({
    data: last_7_days_data,
    series: [
      { name: 'Auth Success', color: 'green.500' },
      { name: 'Auth Fail', color: 'red.500' },
      { name: 'Authz Permit', color: 'blue.500' },
      { name: 'Authz Deny', color: 'orange.500' },
      { name: 'Acct Start', color: 'purple.500' },
      { name: 'Acct Stop', color: 'gray.500' },
    ],
  });

  return (
    <Container maxW="full" py={8}>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">TACACS+ Today Authentication Statistics: {new Date().toISOString().split("T")[0]}</Heading>
      </Flex>
      {isLoading ? (
        <Flex justify="center" align="center" height="50vh">
          <Spinner size="xl" />
        </Flex>
      ) : error ? (
        <Box p={4}>
          <Text color="red.500">
            Error fetching statistics: {error.message}
          </Text>
        </Box>
      ) : (
        <Grid
          templateColumns={{
            base: "1fr",
            md: "repeat(4, 1fr)",
            xl: "repeat(4, 1fr)",
          }}
          gap={6}
        >
          <GridItem colSpan={1}>
            <Box p={2} borderWidth="1px" borderRadius="lg" h="100%">
              <Stat.Root>
                <Stat.Label >Today Successful Logins</Stat.Label>
                <Stat.ValueText>{stats?.today_successful_logins}</Stat.ValueText>
              </Stat.Root>
            </Box>
          </GridItem>
          <GridItem colSpan={1}>
            <Box p={2} borderWidth="1px" borderRadius="lg" h="100%">
              <Stat.Root>
                <Stat.Label>Today Unique IP Users</Stat.Label>
                <Stat.ValueText>{stats?.today_unique_user_source_ip_count}</Stat.ValueText>
              </Stat.Root>
            </Box>
          </GridItem>
          <GridItem colSpan={1}>
            <Box p={2} borderWidth="1px" borderRadius="lg" h="100%">
              <Stat.Root>
                <Stat.Label>Today Unique NAS IP</Stat.Label>
                <Stat.ValueText>{stats?.today_unique_nas_ip_count}</Stat.ValueText>
              </Stat.Root>
            </Box>
          </GridItem>
          <GridItem colSpan={1}>
            <Box p={2} borderWidth="1px" borderRadius="lg" h="100%">
              <Stat.Root>
                <Stat.Label>Today Failed Logins</Stat.Label>
                <Stat.ValueText
                  color={stats?.today_failed_logins && stats?.today_failed_logins > 0 ? "red" : "green"}
                >
                  {stats?.today_failed_logins}
                </Stat.ValueText>
              </Stat.Root>
            </Box>
          </GridItem>

          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                Top 5 Users Login Success
              </Heading>
              <Chart.Root mx="auto" chart={chart_authentication_success_count_by_user}>
                <PieChart>
                  <Tooltip
                    cursor={false}
                    animationDuration={100}
                    content={<Chart.Tooltip hideLabel />}
                  />
                  <Legend content={<Chart.Legend />} />
                  <Pie
                    isAnimationActive={false}
                    data={chart_authentication_success_count_by_user.data}
                    dataKey={chart_authentication_success_count_by_user.key("value")}
                  >
                    <LabelList position="inside" fill="white" stroke="none" />
                    {chart_authentication_success_count_by_user.data.map((item, index) => (
                      <Cell key={index} fill={chart_authentication_success_count_by_user.color(item.color)} />
                    ))}
                  </Pie>
                </PieChart>
              </Chart.Root>
            </Box>
          </GridItem>
          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                Top 5 Source IPs Login Success
              </Heading>
              <Chart.Root mx="auto" chart={chart_authentication_success_count_by_user_source_ip}>
                <PieChart>
                  <Tooltip
                    cursor={false}
                    animationDuration={100}
                    content={<Chart.Tooltip hideLabel />}
                  />
                  <Legend content={<Chart.Legend />} />
                  <Pie
                    isAnimationActive={false}
                    data={chart_authentication_success_count_by_user_source_ip.data}
                    dataKey={chart_authentication_success_count_by_user_source_ip.key("value")}
                  >
                    <LabelList position="inside" fill="white" stroke="none" />
                    {chart_authentication_success_count_by_user_source_ip.data.map((item, index) => (
                      <Cell key={index} fill={chart_authentication_success_count_by_user_source_ip.color(item.color)} />
                    ))}
                  </Pie>
                </PieChart>
              </Chart.Root>
            </Box>
          </GridItem>
          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                Top 5 NAS IPs Login Success
              </Heading>
              <Chart.Root mx="auto" chart={chart_authentication_success_count_by_nas_ip}>
                <PieChart>
                  <Tooltip
                    cursor={false}
                    animationDuration={100}
                    content={<Chart.Tooltip hideLabel />}
                  />
                  <Legend content={<Chart.Legend />} />
                  <Pie
                    isAnimationActive={false}
                    data={chart_authentication_success_count_by_nas_ip.data}
                    dataKey={chart_authentication_success_count_by_nas_ip.key("value")}
                  >
                    <LabelList position="inside" fill="white" stroke="none" />
                    {chart_authentication_success_count_by_nas_ip.data.map((item, index) => (
                      <Cell key={index} fill={chart_authentication_success_count_by_nas_ip.color(item.color)} />
                    ))}
                  </Pie>
                </PieChart>
              </Chart.Root>
            </Box>
          </GridItem>
          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                Top 5 Users - Failed Login Attempts
              </Heading>
              <Chart.Root mx="auto" chart={chart_authentication_failed_count_by_user}>
                <PieChart>
                  <Tooltip
                    cursor={false}
                    animationDuration={100}
                    content={<Chart.Tooltip hideLabel />}
                  />
                  <Legend content={<Chart.Legend />} />
                  <Pie
                    isAnimationActive={false}
                    data={chart_authentication_failed_count_by_user.data}
                    dataKey={chart_authentication_failed_count_by_user.key("value")}
                  >
                    <LabelList position="inside" fill="white" stroke="none" />
                    {chart_authentication_failed_count_by_user.data.map((item, index) => (
                      <Cell key={index} fill={chart_authentication_failed_count_by_user.color(item.color)} />
                    ))}
                  </Pie>
                </PieChart>
              </Chart.Root>
            </Box>
          </GridItem>

          <GridItem colSpan={{ base: 2, md: 4, xl: 4 }}>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                Last 7 Days AAA Statistics
              </Heading>
              <Chart.Root
                chart={chart_last_7_days}
                height="350px"
              >
                <AreaChart width={800} height={350} data={last_7_days_data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <Tooltip />
                  <Legend />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Area dataKey="Auth Success" type="monotone" fill="var(--chakra-colors-green-500)" stroke="var(--chakra-colors-green-600)" />
                  <Area dataKey="Auth Fail" type="monotone" fill="var(--chakra-colors-red-500)" stroke="var(--chakra-colors-red-600)" />
                  <Area dataKey="Authz Permit" type="monotone" fill="var(--chakra-colors-blue-500)" stroke="var(--chakra-colors-blue-600)" />
                  <Area dataKey="Authz Deny" type="monotone" fill="var(--chakra-colors-orange-500)" stroke="var(--chakra-colors-orange-600)" />
                  <Area dataKey="Acct Start" type="monotone" fill="var(--chakra-colors-purple-500)" stroke="var(--chakra-colors-purple-600)" />
                  <Area dataKey="Acct Stop" type="monotone" fill="var(--chakra-colors-gray-500)" stroke="var(--chakra-colors-gray-600)" />
                </AreaChart>
              </Chart.Root>
            </Box>
          </GridItem>
        </Grid>
      )
      }
    </Container >
  )
}
