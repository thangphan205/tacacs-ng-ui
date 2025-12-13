import {
  Box,
  Container,
  Flex,
  Grid,
  GridItem,
  Heading,
  Input,
  Spinner,
  Text,
} from "@chakra-ui/react"
import { Chart, useChart } from "@chakra-ui/charts"
import { Area, AreaChart, CartesianGrid, Cell, LabelList, Legend, Pie, PieChart, Tooltip, XAxis, YAxis } from "recharts"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import {
  AaaStatisticsService,
} from "@/client"

const today = new Date().toISOString().split("T")[0]

export const Route = createFileRoute("/_layout/aaa_statistics")({
  component: AaaStatistics,
})

export function AaaStatistics() {
  const [startDate, setStartDate] = useState<string>(today)
  const [endDate, setEndDate] = useState<string>(today)

  const {
    data: stats,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["aaa_statistics", startDate, endDate],
    queryFn: () =>
      AaaStatisticsService.readAaaStatistics({
        rangeDate: `${startDate},${endDate}`,
      }),
  })


  const handleStartDateChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setStartDate(event.target.value)
  }

  const handleEndDateChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEndDate(event.target.value)
  }


  const color_chart = ["blue.500", "green.500", "pink.500", "orange.500", "red.500"]
  const data_authentication_success_count_by_user = stats?.authentication_success_count_by_user?.map((user, index) => ({
    name: user.username,
    value: user.success_count,
    color: color_chart[index]
  })) || [];
  const chart_authentication_success_count_by_user = useChart({
    data: data_authentication_success_count_by_user
  })
  const data_authentication_success_count_by_user_source_ip = stats?.authentication_success_count_by_user_source_ip?.map((user, index) => ({
    name: user.user_source_ip,
    value: user.success_count,
    color: color_chart[index]
  })) || [];
  const chart_authentication_success_count_by_user_source_ip = useChart({
    data: data_authentication_success_count_by_user_source_ip
  })

  const color_chart_failed = ["red.500", "orange.500", "pink.500", "green.500", "blue.500"]
  const data_authentication_failed_count_by_user = stats?.authentication_failed_count_by_user?.map((user, index) => ({
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
    'Authz Pass': stats?.last_7_days_authorization_pass?.[index]?.count || 0,
    'Authz Deny': stats?.last_7_days_authorization_deny?.[index]?.count || 0,
    'Acct Start': stats?.last_7_days_accounting?.[index]?.start_count || 0,
    'Acct Stop': stats?.last_7_days_accounting?.[index]?.stop_count || 0,
  })) || [];

  console.log(last_7_days_data);


  const chart_last_7_days = useChart({
    data: last_7_days_data,
    series: [
      { name: 'Auth Success', color: 'green.500' },
      { name: 'Auth Fail', color: 'red.500' },
      { name: 'Authz Pass', color: 'blue.500' },
      { name: 'Authz Deny', color: 'orange.500' },
      { name: 'Acct Start', color: 'purple.500' },
      { name: 'Acct Stop', color: 'gray.500' },
    ],
  });




  return (
    <Container maxW="full" py={8}>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">TACACS+ Authentication Statistics</Heading>
        <Flex gap={4}>
          <Text>From</Text>
          <Input
            placeholder="Start Date"
            size="md"
            type="date"
            value={startDate}
            onChange={handleStartDateChange}
            maxW="200px"
          />
          <Text>To</Text>
          <Input
            placeholder="End Date"
            size="md"
            type="date"
            value={endDate}
            onChange={handleEndDateChange}
            maxW="200px"
            min={startDate}
          />

        </Flex>
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
            md: "repeat(2, 1fr)",
            xl: "repeat(3, 1fr)",
          }}
          gap={6}
        >


          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                Top 5 Users Login Success
              </Heading>
              <Chart.Root boxSize="320px" mx="auto" chart={chart_authentication_success_count_by_user}>
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
              <Chart.Root boxSize="320px" mx="auto" chart={chart_authentication_success_count_by_user_source_ip}>
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
                Top 5 Users - Failed Login Attempts
              </Heading>
              <Chart.Root boxSize="320px" mx="auto" chart={chart_authentication_failed_count_by_user}>
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
          <GridItem colSpan={{ base: 1, md: 2, xl: 3 }}>
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
                  <Area dataKey="Authz Pass" type="monotone" fill="var(--chakra-colors-blue-500)" stroke="var(--chakra-colors-blue-600)" />
                  <Area dataKey="Authz Deny" type="monotone" fill="var(--chakra-colors-orange-500)" stroke="var(--chakra-colors-orange-600)" />
                  <Area dataKey="Acct Start" type="monotone" fill="var(--chakra-colors-purple-500)" stroke="var(--chakra-colors-purple-600)" />
                  <Area dataKey="Acct Stop" type="monotone" fill="var(--chakra-colors-gray-500)" stroke="var(--chakra-colors-gray-600)" />
                </AreaChart>
              </Chart.Root>
            </Box>
          </GridItem>
        </Grid>
      )}
    </Container>
  )
}
