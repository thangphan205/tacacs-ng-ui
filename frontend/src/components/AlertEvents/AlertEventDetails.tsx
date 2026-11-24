import {
  Badge,
  Box,
  Button,
  Code,
  Flex,
  Grid,
  HStack,
  IconButton,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { type ReactNode, useState } from "react"
import {
  FiAlertCircle,
  FiAlertTriangle,
  FiCheck,
  FiCheckCircle,
  FiChevronDown,
  FiChevronRight,
  FiClock,
  FiCode,
  FiCopy,
  FiMinusCircle,
  FiSend,
  FiServer,
  FiXCircle,
} from "react-icons/fi"

import type { AlertEventPublic } from "@/client"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogHeader,
  DialogRoot,
  DialogTitle,
} from "@/components/ui/dialog"
import { formatDateTime } from "@/utils"

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue }

type JsonObject = { [key: string]: JsonValue }

export const SEVERITY_COLORS: Record<string, string> = {
  low: "blue",
  medium: "yellow",
  high: "orange",
  critical: "red",
}

export const STATUS_COLORS: Record<string, string> = {
  sent: "green",
  failed: "red",
  no_channel: "gray",
}

export const STATUS_LABELS: Record<string, string> = {
  sent: "Sent",
  failed: "Failed",
  no_channel: "No channel",
}

const ACTION_COLORS: Record<string, string> = {
  CREATE: "green",
  UPDATE: "blue",
  DELETE: "red",
  ACTIVATE: "teal",
}

// Keys the evaluator writes into `payload_snapshot`
// (backend/app/crud/alert_evaluator.py). Unknown keys fall back to a
// humanised version of the key, so a new rule type still shows its data.
const PAYLOAD_LABELS: Record<string, string> = {
  new_usernames: "New usernames",
  new_source_ips: "New source IPs",
  triggered_ips: "Offending IPs",
  ip: "Source IP",
  fail_count: "Auth failures",
  deny_count: "Authz denials",
  config_change_count: "Config changes",
  changes: "Changes",
  users: "Users",
  unusual_logins: "Unusual logins",
  sources: "Source IPs",
  top_users: "Top users",
  top_sources: "Top source IPs",
  top_devices: "Top devices",
  node: "Node",
  fired_at: "Fired at",
  window_minutes: "Window (min)",
  actions_checked: "Actions",
}

const COLUMN_LABELS: Record<string, string> = {
  action: "Action",
  filename: "Filename",
  entity_id: "Entity ID",
  by: "By",
  ip_address: "IP Address",
  at: "At",
  ip: "IP Address",
  username: "Username",
  usernames: "Usernames",
  source_ips: "Source IPs",
  devices: "Devices",
  success: "Success",
  fail: "Failed",
  fail_count: "Failures",
  first_seen: "First Seen",
  last_seen: "Last Seen",
  login_at: "Login At",
  hour: "Hour",
  share: "Share",
  total_logins: "Total Logins",
  usual_hours: "Usual Hours",
  logins: "Logins",
  name: "Name",
  count: "Count",
}

// The rule name is already in the dialog title.
const HIDDEN_KEYS = new Set(["rule"])

// Context keys rendered in the top metadata strip instead of body sections.
const CONTEXT_KEYS = new Set(["window_minutes", "node", "fired_at"])

const TIMESTAMP_COLUMNS = new Set([
  "at",
  "first_seen",
  "last_seen",
  "login_at",
  "fired_at",
])

const MONO_COLUMNS = new Set([
  "ip",
  "ip_address",
  "filename",
  "entity_id",
  "username",
])

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const ISO_TIMESTAMP_REGEX =
  /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2}| UTC)?$/

const humanize = (key: string): string => {
  const words = key.replace(/_/g, " ")
  return words.charAt(0).toUpperCase() + words.slice(1)
}

const isObject = (v: JsonValue): v is JsonObject =>
  typeof v === "object" && v !== null && !Array.isArray(v)

const isScalar = (v: JsonValue): boolean =>
  v === null ||
  typeof v === "string" ||
  typeof v === "number" ||
  typeof v === "boolean"

function formatHourRanges(hours: number[]): string {
  if (hours.length === 0) return "none yet"
  const unique = Array.from(new Set(hours)).sort((a, b) => a - b)
  if (unique.length === 24) return "all hours"
  const ranges: Array<[number, number]> = []
  for (const h of unique) {
    const last = ranges[ranges.length - 1]
    if (last && last[1] === h) {
      last[1] = h + 1
    } else {
      ranges.push([h, h + 1])
    }
  }
  return ranges
    .map(
      ([s, e]) =>
        `${String(s).padStart(2, "0")}:00–${String(e % 24).padStart(2, "0")}:00`,
    )
    .join(", ")
}

function formatTimestampValue(raw: string): string {
  // Handle "YYYY-MM-DD HH:MM:SS UTC" as well as ISO-8601
  const normalized = raw.endsWith(" UTC")
    ? `${raw.slice(0, -4).replace(" ", "T")}Z`
    : raw
  const formatted = formatDateTime(normalized, { hour12: false }, "")
  return formatted || raw
}

/**
 * Parse `payload_snapshot`. Returns `null` when there is nothing to show and
 * the raw text when it is not a JSON object, so an unexpected value is never
 * silently dropped.
 */
export function parsePayload(
  snapshot: string | null | undefined,
): JsonObject | string | null {
  if (!snapshot) return null
  try {
    const parsed: JsonValue = JSON.parse(snapshot)
    return isObject(parsed) ? parsed : snapshot
  } catch {
    return snapshot
  }
}

/**
 * Build a concise one-line human summary of `payload_snapshot` for the
 * Alert History table.
 */
export function summarizePayload(
  snapshot: string | null | undefined,
): string | null {
  const payload = parsePayload(snapshot)
  if (!payload) return null
  if (typeof payload === "string") return payload

  if (Array.isArray(payload.changes) && payload.changes.length > 0) {
    const first = payload.changes[0]
    const count =
      typeof payload.config_change_count === "number"
        ? payload.config_change_count
        : payload.changes.length
    if (isObject(first)) {
      const action = first.action ? String(first.action) : "CHANGE"
      const target = first.filename
        ? String(first.filename)
        : first.entity_id
          ? String(first.entity_id).slice(0, 8)
          : ""
      const by = first.by ? ` by ${String(first.by)}` : ""
      const prefix = count > 1 ? `${count} changes · ` : ""
      return `${prefix}${action}${target ? ` ${target}` : ""}${by}`
    }
    return `${count} config ${count === 1 ? "change" : "changes"}`
  }

  if (Array.isArray(payload.unusual_logins) && payload.unusual_logins.length) {
    const names = payload.unusual_logins
      .filter(isObject)
      .map((r) => String(r.username ?? "?"))
      .slice(0, 3)
    const extra =
      payload.unusual_logins.length > 3
        ? ` +${payload.unusual_logins.length - 3}`
        : ""
    return `Unusual login hour: ${names.join(", ")}${extra}`
  }

  if (Array.isArray(payload.new_usernames) && payload.new_usernames.length) {
    const list = payload.new_usernames.slice(0, 3).map(String).join(", ")
    const extra =
      payload.new_usernames.length > 3
        ? ` +${payload.new_usernames.length - 3}`
        : ""
    return `New ${payload.new_usernames.length === 1 ? "user" : "users"}: ${list}${extra}`
  }

  if (Array.isArray(payload.new_source_ips) && payload.new_source_ips.length) {
    const list = payload.new_source_ips.slice(0, 2).map(String).join(", ")
    const extra =
      payload.new_source_ips.length > 2
        ? ` +${payload.new_source_ips.length - 2}`
        : ""
    return `New source ${payload.new_source_ips.length === 1 ? "IP" : "IPs"}: ${list}${extra}`
  }

  if (Array.isArray(payload.triggered_ips) && payload.triggered_ips.length) {
    const count = payload.triggered_ips.length
    const ip = payload.ip ? String(payload.ip) : ""
    const fails =
      typeof payload.fail_count === "number"
        ? ` (${payload.fail_count} fails)`
        : ""
    return count === 1 && ip
      ? `${ip}${fails}`
      : `${count} offending IPs${ip ? ` · top ${ip}${fails}` : ""}`
  }

  if (typeof payload.deny_count === "number") {
    const topUser =
      Array.isArray(payload.top_users) &&
      payload.top_users.length > 0 &&
      isObject(payload.top_users[0])
        ? ` · top: ${String(payload.top_users[0].name)}`
        : ""
    return `${payload.deny_count} authz ${payload.deny_count === 1 ? "denial" : "denials"}${topUser}`
  }

  if (typeof payload.fail_count === "number") {
    const topUser =
      Array.isArray(payload.top_users) &&
      payload.top_users.length > 0 &&
      isObject(payload.top_users[0])
        ? ` · top: ${String(payload.top_users[0].name)}`
        : ""
    return `${payload.fail_count} auth ${payload.fail_count === 1 ? "failure" : "failures"}${topUser}`
  }

  return null
}

function CopyableUuid({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  const short = `${value.slice(0, 8)}…${value.slice(-4)}`

  const handleCopy = () => {
    navigator.clipboard?.writeText(value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <HStack gap={1} display="inline-flex" whiteSpace="nowrap">
      <Code
        size="sm"
        variant="surface"
        fontSize="xs"
        fontFamily="mono"
        title={value}
      >
        {short}
      </Code>
      <IconButton
        aria-label="Copy full ID"
        title={copied ? "Copied" : `Copy ${value}`}
        size="2xs"
        variant="ghost"
        colorPalette={copied ? "green" : "gray"}
        onClick={handleCopy}
      >
        {copied ? <FiCheck /> : <FiCopy />}
      </IconButton>
    </HStack>
  )
}

function StatusIcon({ status }: { status?: string }) {
  if (status === "sent") return <FiCheckCircle size={12} />
  if (status === "failed") return <FiXCircle size={12} />
  return <FiMinusCircle size={12} />
}

function CellValue({ column, value }: { column: string; value: JsonValue }) {
  if (value === null || value === "") {
    return (
      <Text as="span" color="fg.muted">
        —
      </Text>
    )
  }

  if (typeof value === "boolean") {
    return (
      <Badge variant="subtle" colorPalette={value ? "green" : "gray"} size="sm">
        {value ? "Yes" : "No"}
      </Badge>
    )
  }

  if (column === "action" && typeof value === "string") {
    return (
      <Badge
        variant="subtle"
        colorPalette={ACTION_COLORS[value.toUpperCase()] ?? "gray"}
        size="sm"
        whiteSpace="nowrap"
      >
        {value}
      </Badge>
    )
  }

  if (column === "success" && typeof value === "number") {
    return (
      <Badge
        variant="subtle"
        colorPalette={value > 0 ? "green" : "gray"}
        size="sm"
        fontVariantNumeric="tabular-nums"
      >
        {value}
      </Badge>
    )
  }

  if (
    (column === "fail" || column === "fail_count") &&
    typeof value === "number"
  ) {
    return (
      <Badge
        variant="subtle"
        colorPalette={value > 0 ? "red" : "gray"}
        size="sm"
        fontVariantNumeric="tabular-nums"
      >
        {value}
      </Badge>
    )
  }

  if (column === "share" && typeof value === "number") {
    return (
      <Text as="span" whiteSpace="nowrap" fontVariantNumeric="tabular-nums">
        {value}%
      </Text>
    )
  }

  if (column === "hour" && typeof value === "number") {
    return (
      <Code size="sm" variant="surface" fontSize="xs" whiteSpace="nowrap">
        {String(value).padStart(2, "0")}:00
      </Code>
    )
  }

  if (
    column === "usual_hours" &&
    Array.isArray(value) &&
    value.every((v) => typeof v === "number")
  ) {
    return (
      <Text as="span" fontSize="xs" whiteSpace="nowrap">
        {formatHourRanges(value as number[])}
      </Text>
    )
  }

  if (
    typeof value === "string" &&
    (TIMESTAMP_COLUMNS.has(column) || ISO_TIMESTAMP_REGEX.test(value))
  ) {
    return (
      <Text
        as="span"
        whiteSpace="nowrap"
        fontVariantNumeric="tabular-nums"
        title={value}
      >
        {formatTimestampValue(value)}
      </Text>
    )
  }

  if (typeof value === "string" && UUID_REGEX.test(value)) {
    return <CopyableUuid value={value} />
  }

  if (Array.isArray(value) && value.every((v) => !isObject(v))) {
    if (value.length === 0) {
      return (
        <Text as="span" color="fg.muted">
          —
        </Text>
      )
    }
    return (
      <Flex gap={1} wrap="wrap">
        {value.map((v, i) => (
          <Code
            key={`${i}-${String(v)}`}
            size="sm"
            variant="surface"
            fontSize="xs"
            whiteSpace="nowrap"
          >
            {String(v)}
          </Code>
        ))}
      </Flex>
    )
  }

  if (typeof value === "object") {
    return (
      <Code fontSize="xs" whiteSpace="pre-wrap">
        {JSON.stringify(value)}
      </Code>
    )
  }

  if (MONO_COLUMNS.has(column)) {
    return (
      <Text
        as="span"
        fontFamily="mono"
        fontSize="xs"
        whiteSpace="nowrap"
        fontWeight={column === "username" ? "medium" : undefined}
      >
        {String(value)}
      </Text>
    )
  }

  return (
    <Text
      as="span"
      whiteSpace={
        typeof value === "number" || String(value).length <= 36
          ? "nowrap"
          : "normal"
      }
      fontVariantNumeric={
        typeof value === "number" ? "tabular-nums" : undefined
      }
    >
      {String(value)}
    </Text>
  )
}

function ObjectRows({ rows }: { rows: JsonObject[] }) {
  const columns = Array.from(new Set(rows.flatMap((r) => Object.keys(r))))

  // Special compact layout for `{name, count}` ranking tables (top_users, top_sources, top_devices)
  const isRankingTable =
    columns.length === 2 &&
    columns.includes("name") &&
    columns.includes("count") &&
    rows.every((r) => typeof r.count === "number")

  if (isRankingTable) {
    const maxCount = Math.max(...rows.map((r) => Number(r.count) || 0), 1)
    return (
      <Box borderWidth="1px" borderRadius="lg" overflow="hidden" bg="bg.panel">
        <VStack align="stretch" gap={0} divideY="1px">
          {rows.map((row, i) => {
            const count = Number(row.count) || 0
            const pct = Math.max(4, Math.round((count / maxCount) * 100))
            return (
              <Flex
                key={i}
                align="center"
                justify="space-between"
                gap={3}
                px={3}
                py={2}
              >
                <Box flex={1} minW={0}>
                  <Text
                    fontSize="xs"
                    fontFamily="mono"
                    fontWeight="medium"
                    truncate
                    mb={1}
                  >
                    {String(row.name ?? "—")}
                  </Text>
                  <Box
                    h="4px"
                    w="full"
                    bg="bg.muted"
                    borderRadius="full"
                    overflow="hidden"
                  >
                    <Box
                      h="full"
                      w={`${pct}%`}
                      bg="teal.solid"
                      borderRadius="full"
                    />
                  </Box>
                </Box>
                <Badge
                  variant="subtle"
                  colorPalette="gray"
                  size="sm"
                  fontVariantNumeric="tabular-nums"
                  flexShrink={0}
                >
                  {count}
                </Badge>
              </Flex>
            )
          })}
        </VStack>
      </Box>
    )
  }

  return (
    <Box overflowX="auto" borderWidth="1px" borderRadius="lg" bg="bg.panel">
      <Table.Root size="sm">
        <Table.Header bg="bg.muted">
          <Table.Row>
            {columns.map((c) => (
              <Table.ColumnHeader
                key={c}
                whiteSpace="nowrap"
                fontSize="xs"
                fontWeight="semibold"
                color="fg.muted"
                py={2.5}
              >
                {COLUMN_LABELS[c] ?? humanize(c)}
              </Table.ColumnHeader>
            ))}
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {rows.map((row, i) => (
            // Rows have no id and the list is read-only, so the index is stable.
            <Table.Row key={i}>
              {columns.map((c) => (
                <Table.Cell key={c} fontSize="xs" py={2.5}>
                  <CellValue column={c} value={row[c] ?? null} />
                </Table.Cell>
              ))}
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
    </Box>
  )
}

function PayloadSection({ label, value }: { label: string; value: JsonValue }) {
  const count = Array.isArray(value) ? value.length : null

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={2}>
        <HStack gap={2}>
          <Text
            fontSize="xs"
            fontWeight="semibold"
            color="fg.muted"
            textTransform="uppercase"
            letterSpacing="wider"
          >
            {label}
          </Text>
          {count !== null && (
            <Badge
              variant="subtle"
              colorPalette="gray"
              size="xs"
              fontVariantNumeric="tabular-nums"
            >
              {count}
            </Badge>
          )}
        </HStack>
      </Flex>

      {Array.isArray(value) ? (
        value.length === 0 ? (
          <Text fontSize="sm" color="fg.muted">
            None
          </Text>
        ) : value.every(isObject) ? (
          <ObjectRows rows={value as JsonObject[]} />
        ) : (
          <Flex gap={1.5} wrap="wrap">
            {value.map((v, i) => (
              <Badge
                key={`${i}-${String(v)}`}
                variant="subtle"
                colorPalette="teal"
                size="md"
                fontFamily="mono"
              >
                {typeof v === "object" ? JSON.stringify(v) : String(v)}
              </Badge>
            ))}
          </Flex>
        )
      ) : (
        <Code
          display="block"
          p={3}
          borderRadius="md"
          fontSize="xs"
          whiteSpace="pre-wrap"
        >
          {JSON.stringify(value, null, 2)}
        </Code>
      )}
    </Box>
  )
}

function MetaItem({
  icon,
  label,
  children,
}: {
  icon?: ReactNode
  label: string
  children: ReactNode
}) {
  return (
    <Box minW={0}>
      <HStack gap={1.5} color="fg.muted" mb={0.5}>
        {icon}
        <Text fontSize="xs" fontWeight="medium">
          {label}
        </Text>
      </HStack>
      <Box fontSize="sm" fontWeight="medium">
        {children}
      </Box>
    </Box>
  )
}

function RawPayloadToggle({ payload }: { payload: JsonObject }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const formatted = JSON.stringify(payload, null, 2)

  const handleCopy = () => {
    navigator.clipboard?.writeText(formatted).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <Box borderTopWidth="1px" pt={3}>
      <Flex align="center" justify="space-between">
        <Button
          size="xs"
          variant="ghost"
          color="fg.muted"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <FiChevronDown /> : <FiChevronRight />}
          <FiCode />
          Raw payload JSON
        </Button>
        {open && (
          <Button
            size="xs"
            variant="ghost"
            colorPalette={copied ? "green" : "gray"}
            onClick={handleCopy}
          >
            {copied ? <FiCheck /> : <FiCopy />}
            {copied ? "Copied" : "Copy JSON"}
          </Button>
        )}
      </Flex>
      {open && (
        <Code
          display="block"
          mt={2}
          p={3}
          borderRadius="lg"
          fontSize="xs"
          whiteSpace="pre"
          overflowX="auto"
          maxH="240px"
          overflowY="auto"
        >
          {formatted}
        </Code>
      )}
    </Box>
  )
}

interface AlertEventDetailsProps {
  event: AlertEventPublic | null
  onClose: () => void
}

/** Dialog showing what made an alert fire (the stored `payload_snapshot`). */
export function AlertEventDetails({ event, onClose }: AlertEventDetailsProps) {
  const payload = event ? parsePayload(event.payload_snapshot) : null
  const payloadObj = payload && typeof payload === "object" ? payload : null

  const scalarMetrics = payloadObj
    ? Object.entries(payloadObj).filter(
        ([k, v]) => !HIDDEN_KEYS.has(k) && !CONTEXT_KEYS.has(k) && isScalar(v),
      )
    : []

  const complexSections = payloadObj
    ? Object.entries(payloadObj).filter(
        ([k, v]) => !HIDDEN_KEYS.has(k) && !CONTEXT_KEYS.has(k) && !isScalar(v),
      )
    : []

  const severityColor = SEVERITY_COLORS[event?.rule_severity ?? ""] ?? "gray"
  const statusColor = STATUS_COLORS[event?.status ?? ""] ?? "gray"
  const statusLabel = STATUS_LABELS[event?.status ?? ""] ?? event?.status ?? "—"

  return (
    <DialogRoot
      placement="center"
      size="xl"
      scrollBehavior="inside"
      open={event !== null}
      onOpenChange={({ open }) => {
        if (!open) onClose()
      }}
    >
      <DialogContent
        maxW="3xl"
        overflow="hidden"
        borderTopWidth="3px"
        borderTopColor={`${severityColor}.solid`}
      >
        <DialogHeader pb={3}>
          <VStack align="start" gap={2} pr={8}>
            <HStack gap={2} wrap="wrap">
              {event?.rule_severity && (
                <Badge
                  colorPalette={severityColor}
                  variant="subtle"
                  size="sm"
                  textTransform="capitalize"
                >
                  <FiAlertCircle size={11} />
                  {event.rule_severity}
                </Badge>
              )}
              {event?.status && (
                <Badge colorPalette={statusColor} variant="subtle" size="sm">
                  <StatusIcon status={event.status} />
                  {statusLabel}
                </Badge>
              )}
            </HStack>
            <DialogTitle fontSize="lg" fontWeight="semibold" lineHeight="short">
              {event?.rule_name ?? "Alert details"}
            </DialogTitle>
          </VStack>
        </DialogHeader>

        <DialogBody pb={6}>
          {event && (
            <VStack align="stretch" gap={5}>
              {/* Delivery error banner */}
              {event.error_message && (
                <Box
                  bg="red.subtle"
                  borderWidth="1px"
                  borderColor="red.muted"
                  borderRadius="lg"
                  p={3}
                >
                  <HStack gap={2} color="red.fg" mb={1}>
                    <FiAlertTriangle size={14} />
                    <Text fontSize="xs" fontWeight="semibold">
                      Delivery error
                    </Text>
                  </HStack>
                  <Text
                    color="red.fg"
                    fontSize="sm"
                    wordBreak="break-word"
                    fontFamily="mono"
                  >
                    {event.error_message}
                  </Text>
                </Box>
              )}

              {/* Context metadata strip */}
              <Box bg="bg.subtle" borderWidth="1px" borderRadius="lg" p={3.5}>
                <Grid
                  templateColumns={{
                    base: "repeat(2, 1fr)",
                    md: "repeat(3, 1fr)",
                  }}
                  gap={3.5}
                >
                  <MetaItem icon={<FiClock size={12} />} label="Triggered at">
                    <Text
                      fontSize="xs"
                      fontVariantNumeric="tabular-nums"
                      whiteSpace="nowrap"
                    >
                      {event.triggered_at
                        ? formatDateTime(event.triggered_at, {
                            hour12: false,
                          })
                        : "—"}
                    </Text>
                  </MetaItem>

                  <MetaItem icon={<FiSend size={12} />} label="Channel">
                    {event.channel_name ? (
                      <Text fontSize="xs" truncate title={event.channel_name}>
                        {event.channel_name}
                      </Text>
                    ) : (
                      <Text fontSize="xs" color="fg.muted" fontStyle="italic">
                        {event.status === "no_channel"
                          ? "No channel configured"
                          : "Deleted channel"}
                      </Text>
                    )}
                  </MetaItem>

                  {payloadObj?.node !== undefined &&
                    payloadObj.node !== null && (
                      <MetaItem icon={<FiServer size={12} />} label="Node">
                        <Code size="sm" variant="surface" fontSize="xs">
                          {String(payloadObj.node)}
                        </Code>
                      </MetaItem>
                    )}

                  {payloadObj?.window_minutes !== undefined &&
                    payloadObj.window_minutes !== null && (
                      <MetaItem
                        icon={<FiClock size={12} />}
                        label="Window (min)"
                      >
                        <Text fontSize="xs" fontVariantNumeric="tabular-nums">
                          {String(payloadObj.window_minutes)}
                        </Text>
                      </MetaItem>
                    )}

                  {payloadObj?.fired_at !== undefined &&
                    payloadObj.fired_at !== null && (
                      <MetaItem icon={<FiClock size={12} />} label="Fired at">
                        <Text
                          fontSize="xs"
                          fontVariantNumeric="tabular-nums"
                          whiteSpace="nowrap"
                          title={String(payloadObj.fired_at)}
                        >
                          {formatTimestampValue(String(payloadObj.fired_at))}
                        </Text>
                      </MetaItem>
                    )}
                </Grid>
              </Box>

              {/* Scalar highlight metrics */}
              {scalarMetrics.length > 0 && (
                <Flex gap={3} wrap="wrap">
                  {scalarMetrics.map(([key, value]) => (
                    <Box
                      key={key}
                      borderWidth="1px"
                      borderRadius="lg"
                      px={4}
                      py={2.5}
                      bg="bg.panel"
                      minW="130px"
                    >
                      <Text
                        fontSize="xs"
                        fontWeight="medium"
                        color="fg.muted"
                        mb={0.5}
                      >
                        {PAYLOAD_LABELS[key] ?? humanize(key)}
                      </Text>
                      <Text
                        fontSize={typeof value === "number" ? "xl" : "sm"}
                        fontWeight="bold"
                        fontFamily={key === "ip" ? "mono" : undefined}
                        fontVariantNumeric="tabular-nums"
                      >
                        {value === null ? "—" : String(value)}
                      </Text>
                    </Box>
                  ))}
                </Flex>
              )}

              {/* Unparseable raw payload */}
              {typeof payload === "string" && (
                <Box>
                  <Text
                    fontSize="xs"
                    fontWeight="semibold"
                    color="fg.muted"
                    textTransform="uppercase"
                    letterSpacing="wider"
                    mb={2}
                  >
                    Details (raw)
                  </Text>
                  <Code
                    display="block"
                    p={3}
                    borderRadius="lg"
                    fontSize="xs"
                    whiteSpace="pre-wrap"
                    wordBreak="break-word"
                  >
                    {payload}
                  </Code>
                </Box>
              )}

              {/* Empty payload */}
              {payload === null && (
                <Box
                  borderWidth="1px"
                  borderStyle="dashed"
                  borderRadius="lg"
                  p={6}
                  textAlign="center"
                >
                  <Text color="fg.muted" fontSize="sm">
                    No details were recorded for this alert.
                  </Text>
                </Box>
              )}

              {/* Structured payload tables & tag lists */}
              {complexSections.map(([key, value]) => (
                <PayloadSection
                  key={key}
                  label={PAYLOAD_LABELS[key] ?? humanize(key)}
                  value={value}
                />
              ))}

              {/* Collapsible raw JSON inspector */}
              {payloadObj && <RawPayloadToggle payload={payloadObj} />}
            </VStack>
          )}
        </DialogBody>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}
