import {
  Box,
  Container,
  DataList,
  Flex,
  Grid,
  GridItem,
  Heading,
  Input,
  Spinner,
  Table,
  Text,
  Tag
} from "@chakra-ui/react"
import { Chart, useChart } from "@chakra-ui/charts"
import { Cell, LabelList, Legend, Pie, PieChart, Tooltip } from "recharts"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import {
  type ApiError,
  type TacacsFileLogStatistics,
  TacacsStatisticsService,
} from "@/client"

const today = new Date().toISOString().split("T")[0]

export const Route = createFileRoute("/_layout/tacacs_statistics")({
  component: TacacsStatistics,
})

export function TacacsStatistics() {
  const [selectedDate, setSelectedDate] = useState<string>(today)

  const {
    data: stats,
    isLoading,
    error,
  } = useQuery<TacacsFileLogStatistics, ApiError>({
    queryKey: ["tacacs_statistics", selectedDate],
    queryFn: () =>
      TacacsStatisticsService.getTacacsLogsStatistics({ dateStr: selectedDate }),
  })
  console.log(stats);

  const handleDateChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedDate(event.target.value)
  }


  const color_chart = ["blue.500", "orange.500", "pink.500", "green.500", "red.500"]
  const data_top_successful_login_users = stats?.top_successful_login_users.map((user, index) => ({
    name: user.name,
    value: user.count,
    color: color_chart[index]
  })) || []
  const chart_top_successful_login_users = useChart({
    data: data_top_successful_login_users
  })

  const data_top_nas_ips = stats?.top_nas_ips.map((user, index) => ({
    name: user.name,
    value: user.count,
    color: color_chart[index]
  })) || []

  const chart_top_nas_ips = useChart({
    data: data_top_nas_ips
  })

  const data_top_access_ips = stats?.top_access_ips.map((item, index) => ({
    name: item.name,
    value: item.count,
    color: color_chart[index]
  })) || []

  const chart_top_access_ips = useChart({
    data: data_top_access_ips
  })

  const stats_summary = [
    { label: "Entries log", value: stats?.parsed_line_count },
    { label: "Successful logins", value: stats?.log_summary.successful },
    { label: "Failed logins", value: stats?.log_summary.failed }
  ]
  return (
    <Container maxW="full" py={8}>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">TACACS+ Authentication Statistics</Heading>
        <Box>
          <Input
            placeholder="Select Date"
            size="md"
            type="date"
            value={selectedDate}
            onChange={handleDateChange}
            maxW="200px"
          />
        </Box>
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
                Top 5 Successful Login Users
              </Heading>
              <Chart.Root boxSize="320px" mx="auto" chart={chart_top_successful_login_users}>
                <PieChart>
                  <Tooltip
                    cursor={false}
                    animationDuration={100}
                    content={<Chart.Tooltip hideLabel />}
                  />
                  <Legend content={<Chart.Legend />} />
                  <Pie
                    isAnimationActive={false}
                    data={chart_top_successful_login_users.data}
                    dataKey={chart_top_successful_login_users.key("value")}
                  >
                    <LabelList position="inside" fill="white" stroke="none" />
                    {chart_top_successful_login_users.data.map((item) => (
                      <Cell key={item.name} fill={chart_top_successful_login_users.color(item.color)} />
                    ))}
                  </Pie>
                </PieChart>
              </Chart.Root>
            </Box>
          </GridItem>
          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                Top 5 NAS IP
              </Heading>
              <Chart.Root boxSize="320px" mx="auto" chart={chart_top_nas_ips}>
                <PieChart>
                  <Tooltip
                    cursor={false}
                    animationDuration={100}
                    content={<Chart.Tooltip hideLabel />}
                  />
                  <Legend content={<Chart.Legend />} />
                  <Pie
                    isAnimationActive={false}
                    data={chart_top_nas_ips.data}
                    dataKey={chart_top_nas_ips.key("value")}
                  >
                    <LabelList position="inside" fill="white" stroke="none" />
                    {chart_top_nas_ips.data.map((item) => (
                      <Cell key={item.name} fill={chart_top_nas_ips.color(item.color)} />
                    ))}
                  </Pie>
                </PieChart>
              </Chart.Root>
            </Box>
          </GridItem>
          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                Top 5 Access IP
              </Heading>
              <Chart.Root boxSize="320px" mx="auto" chart={chart_top_access_ips}>
                <PieChart>
                  <Tooltip
                    cursor={false}
                    animationDuration={100}
                    content={<Chart.Tooltip hideLabel />}
                  />
                  <Legend content={<Chart.Legend />} />
                  <Pie
                    isAnimationActive={false}
                    data={chart_top_access_ips.data}
                    dataKey={chart_top_access_ips.key("value")}
                  >
                    <LabelList position="inside" fill="white" stroke="none" />
                    {chart_top_access_ips.data.map((item) => (
                      <Cell key={item.name} fill={chart_top_access_ips.color(item.color)} />
                    ))}
                  </Pie>
                </PieChart>
              </Chart.Root>
            </Box>
          </GridItem>
          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                Login Summary
              </Heading>
              <DataList.Root orientation="horizontal" divideY="1px" maxW="md">
                {stats_summary.map((item) => (
                  <DataList.Item key={item.label} pt="4">
                    <DataList.ItemLabel>{item.label}</DataList.ItemLabel>
                    <DataList.ItemValue>{item.value}</DataList.ItemValue>
                  </DataList.Item>
                ))}
              </DataList.Root>

            </Box>
          </GridItem>



          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                User Login Breakdown
              </Heading>
              <Table.Root size="sm">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>Username</Table.ColumnHeader>
                    <Table.ColumnHeader>Successful</Table.ColumnHeader>
                    <Table.ColumnHeader >Failed</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {stats?.user_login_breakdown.map((item, index) => (
                    <Table.Row key={index}>
                      <Table.Cell>{item.user}</Table.Cell>
                      <Table.Cell>{item.successful}</Table.Cell>
                      <Table.Cell>{item.failed > 0 ? (
                        <Tag.Root size="md" colorPalette="red" variant="solid">
                          <Tag.Label>{item.failed}</Tag.Label>
                        </Tag.Root>
                      ) : item.failed}</Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>

            </Box>
          </GridItem>

          <GridItem>
            <Box p={4} borderWidth="1px" borderRadius="lg" h="100%">
              <Heading size="md" mb={4}>
                IP Access by users
              </Heading>
              <Table.Root size="sm">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>IP Address</Table.ColumnHeader>
                    <Table.ColumnHeader>Users</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {stats?.ip_access_by_users && Object.entries(stats.ip_access_by_users).map(([ip, users]) => (
                    <Table.Row key={ip}>
                      <Table.Cell>{ip}</Table.Cell>
                      <Table.Cell>
                        {users.join(", ")}
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>

            </Box>
          </GridItem>





        </Grid>
      )}
    </Container>
  )
}
