import { Badge, Box, Code, Flex, Table, Text, VStack } from "@chakra-ui/react"
import type { ReactNode } from "react"

import type { AlertEventPublic } from "@/client"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogHeader,
  DialogRoot,
  DialogTitle,
} from "@/components/ui/dialog"

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue }

type JsonObject = { [key: string]: JsonValue }

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

// The rule name is already in the dialog title.
const HIDDEN_KEYS = new Set(["rule"])

const humanize = (key: string): string => {
  const words = key.replace(/_/g, " ")
  return words.charAt(0).toUpperCase() + words.slice(1)
}

const isObject = (v: JsonValue): v is JsonObject =>
  typeof v === "object" && v !== null && !Array.isArray(v)

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

function Scalar({ value }: { value: JsonValue }) {
  if (value === null) return <Text color="fg.muted">—</Text>
  if (typeof value === "boolean") return <Text>{value ? "yes" : "no"}</Text>
  // e.g. the source IPs or devices of one user row
  if (Array.isArray(value) && value.every((v) => !isObject(v))) {
    return value.length === 0 ? (
      <Text color="fg.muted">—</Text>
    ) : (
      <Text wordBreak="break-all">{value.map(String).join(", ")}</Text>
    )
  }
  if (typeof value === "object") {
    return (
      <Code fontSize="xs" whiteSpace="pre-wrap">
        {JSON.stringify(value)}
      </Code>
    )
  }
  return <Text wordBreak="break-all">{String(value)}</Text>
}

function ObjectRows({ rows }: { rows: JsonObject[] }) {
  const columns = Array.from(new Set(rows.flatMap((r) => Object.keys(r))))
  return (
    <Table.Root size="sm" variant="outline">
      <Table.Header>
        <Table.Row>
          {columns.map((c) => (
            <Table.ColumnHeader key={c}>{humanize(c)}</Table.ColumnHeader>
          ))}
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {rows.map((row, i) => (
          // Rows have no id and the list is read-only, so the index is stable.
          <Table.Row key={i}>
            {columns.map((c) => (
              <Table.Cell key={c} fontSize="xs">
                <Scalar value={row[c] ?? null} />
              </Table.Cell>
            ))}
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  )
}

function PayloadValue({ value }: { value: JsonValue }) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <Text color="fg.muted">none</Text>
    if (value.every(isObject))
      return <ObjectRows rows={value as JsonObject[]} />
    return (
      <Flex gap={1} wrap="wrap">
        {value.map((v, i) => (
          <Badge key={`${i}-${String(v)}`} variant="subtle" size="md">
            {typeof v === "object" ? JSON.stringify(v) : String(v)}
          </Badge>
        ))}
      </Flex>
    )
  }
  return <Scalar value={value} />
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Box>
      <Text fontSize="xs" fontWeight="semibold" color="fg.muted" mb={1}>
        {label}
      </Text>
      {children}
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
  const entries =
    payload && typeof payload === "object"
      ? Object.entries(payload).filter(([k]) => !HIDDEN_KEYS.has(k))
      : []

  return (
    <DialogRoot
      placement="center"
      size="lg"
      scrollBehavior="inside"
      open={event !== null}
      onOpenChange={({ open }) => {
        if (!open) onClose()
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{event?.rule_name ?? "Alert details"}</DialogTitle>
        </DialogHeader>
        <DialogBody pb={6}>
          {event && (
            <VStack align="stretch" gap={4}>
              <Flex gap={6} wrap="wrap" fontSize="sm">
                <Field label="Triggered at">
                  <Text>
                    {event.triggered_at
                      ? new Date(event.triggered_at).toLocaleString("en-US", {
                          hour12: false,
                        })
                      : "—"}
                  </Text>
                </Field>
                <Field label="Severity">
                  <Text>{event.rule_severity ?? "—"}</Text>
                </Field>
                <Field label="Channel">
                  <Text>
                    {event.channel_name ??
                      (event.status === "no_channel"
                        ? "No channel configured"
                        : "Deleted channel")}
                  </Text>
                </Field>
                <Field label="Status">
                  <Text>{event.status}</Text>
                </Field>
              </Flex>

              {event.error_message && (
                <Field label="Error">
                  <Text color="red.500" fontSize="sm" wordBreak="break-word">
                    {event.error_message}
                  </Text>
                </Field>
              )}

              {typeof payload === "string" && (
                <Field label="Details (raw)">
                  <Code display="block" p={2} whiteSpace="pre-wrap">
                    {payload}
                  </Code>
                </Field>
              )}

              {payload === null && (
                <Text color="fg.muted" fontSize="sm">
                  No details were recorded for this alert.
                </Text>
              )}

              {entries.map(([key, value]) => (
                <Field key={key} label={PAYLOAD_LABELS[key] ?? humanize(key)}>
                  <PayloadValue value={value} />
                </Field>
              ))}
            </VStack>
          )}
        </DialogBody>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}
