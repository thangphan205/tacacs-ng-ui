import {
  Badge,
  EmptyState,
  Flex,
  Input,
  InputGroup,
  Select,
  Spinner,
  Table,
  VStack,
  createListCollection,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { FiSearch } from "react-icons/fi"
import type { TacacsLogEvent } from "@/client"
import { TacacsLogsService } from "@/client"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"

const PER_PAGE = 20

const TYPE_COLORS: Record<string, string> = {
  authentication: "purple",
  authorization: "cyan",
  accounting: "yellow",
}

const RESULT_COLORS: Record<string, string> = {
  success: "green",
  failed: "red",
  permit: "teal",
  deny: "orange",
  start: "blue",
  stop: "gray",
  unknown: "gray",
}

const LOG_TYPE_LABEL: Record<string, string> = {
  authentication: "AUTH",
  authorization: "AUTHZ",
  accounting: "ACCT",
}

const logTypeCollection = createListCollection({
  items: [
    { value: "all", label: "All Types" },
    { value: "authentication", label: "Authentication" },
    { value: "authorization", label: "Authorization" },
    { value: "accounting", label: "Accounting" },
  ],
})

const resultCollection = createListCollection({
  items: [
    { value: "", label: "All Results" },
    { value: "success", label: "Success" },
    { value: "failed", label: "Failed" },
    { value: "permit", label: "Permit" },
    { value: "deny", label: "Deny" },
    { value: "start", label: "Start" },
    { value: "stop", label: "Stop" },
  ],
})

export default function TacacsLogEventsTable() {
  const [page, setPage] = useState(1)
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [logType, setLogType] = useState("all")
  const [result, setResult] = useState("")
  const [usernameInput, setUsernameInput] = useState("")
  const [username, setUsername] = useState("")
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setUsername(usernameInput)
      setPage(1)
    }, 500)
  }, [usernameInput])

  const { data, isLoading } = useQuery({
    queryKey: ["tacacs_log_events", { page, date, logType, result, username }],
    queryFn: () =>
      TacacsLogsService.listLogEvents({
        date,
        logType: logType === "all" ? undefined : logType,
        result: result || undefined,
        username: username || undefined,
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
      }),
    placeholderData: (prev) => prev,
  })

  const events = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <VStack align="stretch" gap={4} mt={4}>
      <Flex gap={3} flexWrap="wrap">
        <Input
          type="date"
          value={date}
          onChange={(e) => {
            setDate(e.target.value)
            setPage(1)
          }}
          size="sm"
          maxW="160px"
        />

        <Select.Root
          collection={logTypeCollection}
          value={[logType]}
          onValueChange={({ value }) => {
            setLogType(value[0] ?? "all")
            setPage(1)
          }}
          size="sm"
          maxW="180px"
        >
          <Select.Control>
            <Select.Trigger>
              <Select.ValueText />
            </Select.Trigger>
            <Select.IndicatorGroup>
              <Select.Indicator />
            </Select.IndicatorGroup>
          </Select.Control>
          <Select.Positioner>
            <Select.Content>
              <Select.ItemGroup>
                {logTypeCollection.items.map((item) => (
                  <Select.Item key={item.value} item={item.value}>
                    {item.label}
                    <Select.ItemIndicator />
                  </Select.Item>
                ))}
              </Select.ItemGroup>
            </Select.Content>
          </Select.Positioner>
        </Select.Root>

        <Select.Root
          collection={resultCollection}
          value={[result]}
          onValueChange={({ value }) => {
            setResult(value[0] ?? "")
            setPage(1)
          }}
          size="sm"
          maxW="160px"
        >
          <Select.Control>
            <Select.Trigger>
              <Select.ValueText placeholder="All Results" />
            </Select.Trigger>
            <Select.IndicatorGroup>
              <Select.Indicator />
            </Select.IndicatorGroup>
          </Select.Control>
          <Select.Positioner>
            <Select.Content>
              <Select.ItemGroup>
                {resultCollection.items.map((item) => (
                  <Select.Item key={item.value} item={item.value}>
                    {item.label}
                    <Select.ItemIndicator />
                  </Select.Item>
                ))}
              </Select.ItemGroup>
            </Select.Content>
          </Select.Positioner>
        </Select.Root>

        <InputGroup maxW="200px">
          <Input
            placeholder="Search username..."
            value={usernameInput}
            onChange={(e) => setUsernameInput(e.target.value)}
            size="sm"
          />
        </InputGroup>
      </Flex>

      {isLoading ? (
        <Flex justify="center" py={8}>
          <Spinner />
        </Flex>
      ) : events.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>No events found</EmptyState.Title>
              <EmptyState.Description>
                No log events match the current filters for {date}.
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Timestamp</Table.ColumnHeader>
                <Table.ColumnHeader>Type</Table.ColumnHeader>
                <Table.ColumnHeader>Username</Table.ColumnHeader>
                <Table.ColumnHeader>NAS IP</Table.ColumnHeader>
                <Table.ColumnHeader>Client IP</Table.ColumnHeader>
                <Table.ColumnHeader>Result</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {events.map((event: TacacsLogEvent, idx: number) => (
                <Table.Row key={idx}>
                  <Table.Cell fontFamily="mono" fontSize="xs" whiteSpace="nowrap">
                    {event.timestamp}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={TYPE_COLORS[event.log_type] ?? "gray"} size="sm">
                      {LOG_TYPE_LABEL[event.log_type] ?? event.log_type.toUpperCase()}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>{event.username}</Table.Cell>
                  <Table.Cell fontFamily="mono" fontSize="xs">
                    {event.nas_ip}
                  </Table.Cell>
                  <Table.Cell fontFamily="mono" fontSize="xs">
                    {event.client_ip}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      colorPalette={RESULT_COLORS[event.result] ?? "gray"}
                      size="sm"
                    >
                      {event.result.toUpperCase()}
                    </Badge>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>

          <Flex justifyContent="flex-end">
            <PaginationRoot
              count={count}
              pageSize={PER_PAGE}
              page={page}
              onPageChange={({ page: p }) => setPage(p)}
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
    </VStack>
  )
}
