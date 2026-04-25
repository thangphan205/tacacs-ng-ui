import {
  Badge,
  Box,
  Button,
  Code,
  EmptyState,
  Flex,
  Input,
  InputGroup,
  Select,
  Spinner,
  Table,
  Text,
  VStack,
  createListCollection,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { FiSearch, FiUser } from "react-icons/fi"
import { MdLayers } from "react-icons/md"
import type { TacacsLogEvent } from "@/client"
import { TacacsLogsService } from "@/client"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"
import {
  DrawerBackdrop,
  DrawerBody,
  DrawerCloseTrigger,
  DrawerContent,
  DrawerHeader,
  DrawerRoot,
  DrawerTitle,
} from "@/components/ui/drawer"

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

// ─── Event Detail Drawer ────────────────────────────────────────────────────

interface EventDetailDrawerProps {
  event: TacacsLogEvent | null
  allEvents: TacacsLogEvent[]
  open: boolean
  onClose: () => void
}

function EventDetailDrawer({
  event,
  allEvents,
  open,
  onClose,
}: EventDetailDrawerProps) {
  if (!event) return null

  // Session grouping: find all events in the current page with the same session_id
  const sessionEvents = event.session_id
    ? allEvents
        .filter((e) => e.session_id === event.session_id)
        .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
    : []

  return (
    <DrawerRoot
      open={open}
      onOpenChange={({ open: o }) => !o && onClose()}
      placement="end"
      size="md"
    >
      <DrawerBackdrop />
      <DrawerContent>
        <DrawerCloseTrigger />
        <DrawerHeader borderBottomWidth="1px">
          <DrawerTitle fontSize="md" fontWeight="semibold">
            Event Details
          </DrawerTitle>
        </DrawerHeader>

        <DrawerBody overflowY="auto" py={5} px={5}>
          <VStack align="stretch" gap={5}>
            {/* ── Core fields ── */}
            <Box>
              <Text
                fontSize="xs"
                fontWeight="semibold"
                color="fg.muted"
                mb={2}
                textTransform="uppercase"
                letterSpacing="wide"
              >
                Event Info
              </Text>
              <VStack align="stretch" gap={2} fontSize="sm">
                <Flex justify="space-between">
                  <Text color="fg.muted">Timestamp</Text>
                  <Code fontSize="xs">{event.timestamp}</Code>
                </Flex>
                <Flex justify="space-between">
                  <Text color="fg.muted">Type</Text>
                  <Badge
                    colorPalette={TYPE_COLORS[event.log_type] ?? "gray"}
                    size="sm"
                  >
                    {LOG_TYPE_LABEL[event.log_type] ?? event.log_type.toUpperCase()}
                  </Badge>
                </Flex>
                <Flex justify="space-between">
                  <Text color="fg.muted">Result</Text>
                  <Badge
                    colorPalette={RESULT_COLORS[event.result] ?? "gray"}
                    size="sm"
                  >
                    {event.result.toUpperCase()}
                  </Badge>
                </Flex>
                <Flex justify="space-between">
                  <Text color="fg.muted">Username</Text>
                  <Code fontSize="xs">{event.username}</Code>
                </Flex>
                <Flex justify="space-between">
                  <Text color="fg.muted">NAS IP</Text>
                  <Code fontSize="xs">{event.nas_ip}</Code>
                </Flex>
                <Flex justify="space-between">
                  <Text color="fg.muted">Client IP</Text>
                  <Code fontSize="xs">{event.client_ip}</Code>
                </Flex>
                {event.port && (
                  <Flex justify="space-between">
                    <Text color="fg.muted">Port / TTY</Text>
                    <Code fontSize="xs">{event.port}</Code>
                  </Flex>
                )}
              </VStack>
            </Box>

            {/* ── Command ── */}
            {event.command && (
              <Box>
                <Text
                  fontSize="xs"
                  fontWeight="semibold"
                  color="fg.muted"
                  mb={2}
                  textTransform="uppercase"
                  letterSpacing="wide"
                >
                  Command
                </Text>
                <Code
                  display="block"
                  whiteSpace="pre-wrap"
                  wordBreak="break-all"
                  p={3}
                  borderRadius="md"
                  fontSize="xs"
                  bg="bg.subtle"
                >
                  {event.command}
                </Code>
              </Box>
            )}

            {/* ── Raw Message ── */}
            <Box>
              <Text
                fontSize="xs"
                fontWeight="semibold"
                color="fg.muted"
                mb={2}
                textTransform="uppercase"
                letterSpacing="wide"
              >
                Raw Message
              </Text>
              <Code
                display="block"
                whiteSpace="pre-wrap"
                wordBreak="break-all"
                p={3}
                borderRadius="md"
                fontSize="xs"
                bg="bg.subtle"
              >
                {event.message}
              </Code>
            </Box>

            {/* ── Session Timeline ── */}
            {sessionEvents.length > 1 && (
              <Box>
                <Flex align="center" gap={2} mb={3}>
                  <MdLayers />
                  <Text
                    fontSize="xs"
                    fontWeight="semibold"
                    color="fg.muted"
                    textTransform="uppercase"
                    letterSpacing="wide"
                  >
                    Session Timeline ({sessionEvents.length} events)
                  </Text>
                </Flex>
                <VStack align="stretch" gap={2}>
                  {sessionEvents.map((ev, idx) => (
                    <Flex
                      key={idx}
                      gap={3}
                      p={2}
                      borderRadius="md"
                      borderWidth="1px"
                      borderColor={
                        ev === event ? "colorPalette.300" : "border.subtle"
                      }
                      bg={ev === event ? "colorPalette.50" : "transparent"}
                      _dark={{
                        bg:
                          ev === event ? "colorPalette.900" : "transparent",
                      }}
                      align="flex-start"
                    >
                      <Box flex="none" mt={0.5}>
                        <Badge
                          colorPalette={TYPE_COLORS[ev.log_type] ?? "gray"}
                          size="sm"
                        >
                          {LOG_TYPE_LABEL[ev.log_type] ??
                            ev.log_type.toUpperCase()}
                        </Badge>
                      </Box>
                      <VStack align="stretch" gap={0.5} flex={1} minW={0}>
                        <Code fontSize="xs" color="fg.muted">
                          {ev.timestamp.slice(11, 19)}
                        </Code>
                        {ev.command ? (
                          <Text fontSize="xs" fontFamily="mono" truncate>
                            {ev.command}
                          </Text>
                        ) : (
                          <Text
                            fontSize="xs"
                            color="fg.muted"
                            fontStyle="italic"
                            truncate
                          >
                            {ev.message.slice(0, 60)}
                          </Text>
                        )}
                      </VStack>
                      <Badge
                        colorPalette={RESULT_COLORS[ev.result] ?? "gray"}
                        size="sm"
                        flex="none"
                      >
                        {ev.result.toUpperCase()}
                      </Badge>
                    </Flex>
                  ))}
                </VStack>
              </Box>
            )}
          </VStack>
        </DrawerBody>
      </DrawerContent>
    </DrawerRoot>
  )
}

// ─── Main Table ─────────────────────────────────────────────────────────────

export default function TacacsLogEventsTable() {
  const today = new Date().toISOString().slice(0, 10)
  const [page, setPage] = useState(1)
  const [date, setDate] = useState(today)
  const [logType, setLogType] = useState("all")
  const [result, setResult] = useState("")
  const [usernameInput, setUsernameInput] = useState("")
  const [username, setUsername] = useState("")
  const [selectedEvent, setSelectedEvent] = useState<TacacsLogEvent | null>(
    null,
  )
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

  // Clicking a username badge sets the username filter
  const handleUsernameClick = (u: string) => {
    setUsernameInput(u)
    setUsername(u)
    setPage(1)
  }

  return (
    <>
      <VStack align="stretch" gap={4} mt={4}>
        <Flex gap={3} flexWrap="wrap" align="center">
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

          <InputGroup maxW="220px">
            <Input
              placeholder="Search username..."
              value={usernameInput}
              onChange={(e) => setUsernameInput(e.target.value)}
              size="sm"
            />
          </InputGroup>

          {/* Active username filter chip */}
          {username && (
            <Flex align="center" gap={1}>
              <Badge
                colorPalette="blue"
                size="sm"
                variant="subtle"
                display="flex"
                alignItems="center"
                gap={1}
              >
                <FiUser />
                {username}
              </Badge>
              <Button
                size="xs"
                variant="ghost"
                onClick={() => {
                  setUsernameInput("")
                  setUsername("")
                  setPage(1)
                }}
              >
                ✕
              </Button>
            </Flex>
          )}
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
                  <Table.ColumnHeader>Port</Table.ColumnHeader>
                  <Table.ColumnHeader>NAS IP</Table.ColumnHeader>
                  <Table.ColumnHeader>Command / Message</Table.ColumnHeader>
                  <Table.ColumnHeader>Result</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {events.map((event: TacacsLogEvent, idx: number) => (
                  <Table.Row
                    key={idx}
                    cursor="pointer"
                    _hover={{ bg: "bg.subtle" }}
                    onClick={() => setSelectedEvent(event)}
                  >
                    <Table.Cell
                      fontFamily="mono"
                      fontSize="xs"
                      whiteSpace="nowrap"
                    >
                      {event.timestamp}
                    </Table.Cell>
                    <Table.Cell>
                      <Badge
                        colorPalette={TYPE_COLORS[event.log_type] ?? "gray"}
                        size="sm"
                      >
                        {LOG_TYPE_LABEL[event.log_type] ??
                          event.log_type.toUpperCase()}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell>
                      {/* Clickable username badge — sets the username filter */}
                      <Badge
                        variant="subtle"
                        colorPalette="blue"
                        size="sm"
                        cursor="pointer"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleUsernameClick(event.username)
                        }}
                        _hover={{ opacity: 0.75 }}
                        title={`Filter by ${event.username}`}
                        display="inline-flex"
                        alignItems="center"
                        gap={1}
                      >
                        <FiUser />
                        {event.username}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell fontFamily="mono" fontSize="xs" color="fg.muted">
                      {event.port ?? "—"}
                    </Table.Cell>
                    <Table.Cell fontFamily="mono" fontSize="xs">
                      {event.nas_ip}
                    </Table.Cell>
                    <Table.Cell maxW="280px">
                      {event.command ? (
                        <Text
                          fontSize="xs"
                          fontFamily="mono"
                          truncate
                          title={event.command}
                        >
                          {event.command}
                        </Text>
                      ) : (
                        <Text
                          fontSize="xs"
                          color="fg.muted"
                          fontStyle="italic"
                          truncate
                          title={event.message}
                        >
                          {event.message.length > 60
                            ? `${event.message.slice(0, 60)}…`
                            : event.message}
                        </Text>
                      )}
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

            <Flex justifyContent="space-between" align="center">
              <Text fontSize="xs" color="fg.muted">
                Click any row to see details · Click a username badge to filter
              </Text>
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

      {/* Event Detail Drawer */}
      <EventDetailDrawer
        event={selectedEvent}
        allEvents={events}
        open={selectedEvent !== null}
        onClose={() => setSelectedEvent(null)}
      />
    </>
  )
}
