import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Container,
  Flex,
  Heading,
  HStack,
  Input,
  NativeSelect,
  SimpleGrid,
  Switch,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { FiSend } from "react-icons/fi"

import type { ApiError } from "@/api"
import {
  type SiemConfigPublic,
  type SiemConfigUpdate,
  SiemService,
} from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import { Field } from "@/components/ui/field"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { formatDateTime, handleError } from "@/utils"

export const Route = createFileRoute("/_layout/admin/siem")({
  component: SiemPage,
})

type ShipKey =
  | "ship_access"
  | "ship_authentication"
  | "ship_authorization"
  | "ship_accounting"
  | "ship_audit"

const TACACS_SOURCES: { key: ShipKey; label: string; hint: string }[] = [
  {
    key: "ship_authentication",
    label: "Authentication",
    hint: "Logins: succeeded, failed, denied",
  },
  {
    key: "ship_authorization",
    label: "Authorization",
    hint: "Commands permitted or denied",
  },
  {
    key: "ship_accounting",
    label: "Accounting",
    hint: "Session and command start / stop",
  },
  { key: "ship_access", label: "Access", hint: "Connection-level events" },
]

interface FormState {
  enabled: boolean
  webhook_url: string
  webhook_token: string
  clear_token: boolean
  webhook_verify_tls: boolean
  syslog_host: string
  syslog_port: string
  syslog_protocol: "udp" | "tcp"
  ship_access: boolean
  ship_authentication: boolean
  ship_authorization: boolean
  ship_accounting: boolean
  ship_audit: boolean
}

function toForm(cfg: SiemConfigPublic): FormState {
  return {
    enabled: cfg.enabled ?? false,
    webhook_url: cfg.webhook_url ?? "",
    webhook_token: "",
    clear_token: false,
    webhook_verify_tls: cfg.webhook_verify_tls ?? true,
    syslog_host: cfg.syslog_host ?? "",
    syslog_port: String(cfg.syslog_port ?? 514),
    syslog_protocol: cfg.syslog_protocol === "tcp" ? "tcp" : "udp",
    ship_access: cfg.ship_access ?? false,
    ship_authentication: cfg.ship_authentication ?? false,
    ship_authorization: cfg.ship_authorization ?? false,
    ship_accounting: cfg.ship_accounting ?? false,
    ship_audit: cfg.ship_audit ?? false,
  }
}

/** The port as a number, or null when the field is empty or not 1–65535. */
function parsePort(value: string): number | null {
  const port = Number(value.trim())
  return value.trim() !== "" &&
    Number.isInteger(port) &&
    port >= 1 &&
    port <= 65535
    ? port
    : null
}

function toUpdate(f: FormState): SiemConfigUpdate {
  const update: SiemConfigUpdate = {
    enabled: f.enabled,
    webhook_url: f.webhook_url.trim(),
    webhook_verify_tls: f.webhook_verify_tls,
    syslog_host: f.syslog_host.trim(),
    syslog_protocol: f.syslog_protocol,
    ship_access: f.ship_access,
    ship_authentication: f.ship_authentication,
    ship_authorization: f.ship_authorization,
    ship_accounting: f.ship_accounting,
    ship_audit: f.ship_audit,
  }
  // An empty port is not sent (the stored one stays); "" would be 0 → 422.
  const port = parsePort(f.syslog_port)
  if (port !== null) update.syslog_port = port
  // Omitted keeps the stored token; "" clears it.
  if (f.clear_token) update.webhook_token = ""
  else if (f.webhook_token) update.webhook_token = f.webhook_token
  return update
}

function formatTime(iso?: string | null): string {
  if (!iso) return "never"
  return formatDateTime(iso)
}

function SwitchRow({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string
  hint?: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <Flex justify="space-between" align="center" gap={4}>
      <Box>
        <Text fontWeight="medium">{label}</Text>
        {hint && (
          <Text fontSize="sm" color="fg.muted">
            {hint}
          </Text>
        )}
      </Box>
      <Switch.Root
        checked={checked}
        disabled={disabled}
        onCheckedChange={(e) => onChange(e.checked)}
      >
        <Switch.HiddenInput aria-label={label} />
        <Switch.Control />
      </Switch.Root>
    </Flex>
  )
}

function StatusCard() {
  const { data: status } = useQuery({
    queryKey: ["siem-status"],
    queryFn: () => SiemService.readSiemStatus(),
    refetchInterval: 10_000,
  })
  const sent = Object.entries(status?.events_sent ?? {})
  return (
    <Card.Root variant="outline">
      <Card.Header pb={2}>
        <HStack justify="space-between">
          <Heading size="sm">Real-time shipper</Heading>
          {status && (
            <Badge colorPalette={status.running ? "green" : "red"}>
              {status.running ? "Running" : "Not running"}
            </Badge>
          )}
        </HStack>
        <Text fontSize="sm" color="fg.muted">
          Status of node <b>{status?.node_name ?? "…"}</b>, the node serving
          this page. Every node runs its own shipper for its own log files.
        </Text>
      </Card.Header>
      <Card.Body>
        <VStack align="stretch" gap={1} fontSize="sm">
          <Text>Last event sent: {formatTime(status?.last_event_at)}</Text>
          <Text>
            Events sent since start:{" "}
            {sent.length === 0
              ? "none"
              : sent.map(([type, n]) => `${type} ${n}`).join(", ")}
          </Text>
          {status?.last_error && (
            <Text color="fg.error">
              Last error ({formatTime(status.last_error_at)}):{" "}
              {status.last_error}
            </Text>
          )}
        </VStack>
      </Card.Body>
    </Card.Root>
  )
}

function SiemPage() {
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [form, setForm] = useState<FormState | null>(null)

  const { data: config } = useQuery({
    queryKey: ["siem-config"],
    queryFn: () => SiemService.readSiemConfig(),
    enabled: !!currentUser?.is_superuser,
  })
  const { data: status } = useQuery({
    queryKey: ["siem-status"],
    queryFn: () => SiemService.readSiemStatus(),
    enabled: !!currentUser?.is_superuser,
  })
  const readOnly = status?.node_role === "standby"

  useEffect(() => {
    if (config) setForm(toForm(config))
  }, [config])

  const save = useMutation({
    mutationFn: (f: FormState) =>
      SiemService.updateSiemConfig({ siemConfigUpdate: toUpdate(f) }),
    onSuccess: (cfg) => {
      queryClient.setQueryData(["siem-config"], cfg)
      showSuccessToast(
        "SIEM settings saved. Every node applies them within about 10 seconds.",
      )
    },
    onError: (err: ApiError) => handleError(err),
  })

  const test = useMutation({
    mutationFn: () => SiemService.testSiem(),
    onSuccess: ({ results }) => {
      for (const r of results) {
        const name = r.sink === "webhook" ? "Webhook" : "Syslog"
        if (r.ok) showSuccessToast(`${name}: test event sent.`)
        else showErrorToast(`${name}: ${r.error ?? "failed"}`)
      }
    },
    onError: (err: ApiError) => handleError(err),
  })

  if (!currentUser?.is_superuser) {
    return <Text p={8}>Access denied.</Text>
  }
  if (!form || !config) {
    return (
      <Container maxW="full">
        <Heading size="md" py={4}>
          SIEM Integration
        </Heading>
      </Container>
    )
  }

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm({ ...form, [key]: value })
  const dirty =
    JSON.stringify(toUpdate(form)) !== JSON.stringify(toUpdate(toForm(config)))
  // Required with a host; without one, only a malformed value is an error.
  const portInvalid =
    parsePort(form.syslog_port) === null &&
    (form.syslog_host.trim() !== "" || form.syslog_port.trim() !== "")
  const noSink = !form.webhook_url.trim() && !form.syslog_host.trim()
  const noSource =
    !form.ship_audit && !TACACS_SOURCES.some(({ key }) => form[key])

  return (
    <Container maxW="full" pb={8}>
      <HStack py={4} gap={3}>
        <Heading size="md">SIEM Integration</Heading>
        <Badge colorPalette={config.enabled ? "green" : "gray"}>
          {config.enabled ? "On" : "Off"}
        </Badge>
      </HStack>
      <Text color="fg.muted" mb={4} maxW="3xl">
        Send each TACACS+ log event and app audit log entry to your SIEM as it
        happens, over an HTTP webhook (Splunk HEC format) and/or syslog (RFC
        5424).
      </Text>

      {readOnly && (
        <Alert.Root status="info" mb={4} borderRadius="md">
          <Alert.Indicator />
          <Alert.Description>
            This node is a standby. Its shipper uses the settings replicated
            from the primary; change them on the primary node.
          </Alert.Description>
        </Alert.Root>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate(form)
        }}
      >
        <fieldset disabled={readOnly}>
          <VStack align="stretch" gap={4}>
            <Card.Root variant="outline">
              <Card.Body>
                <SwitchRow
                  label="Enable SIEM forwarding"
                  hint="Off stops all forwarding. Turning it back on starts from new events; nothing missed while off is replayed."
                  checked={form.enabled}
                  disabled={readOnly}
                  onChange={(v) => set("enabled", v)}
                />
                {form.enabled && noSink && (
                  <Text mt={3} fontSize="sm" color="fg.warning">
                    Set a webhook URL or a syslog host, or nothing is sent.
                  </Text>
                )}
                {form.enabled && noSource && (
                  <Text mt={3} fontSize="sm" color="fg.warning">
                    Choose at least one log source below, or nothing is sent.
                  </Text>
                )}
              </Card.Body>
            </Card.Root>

            <Card.Root variant="outline">
              <Card.Header pb={2}>
                <Heading size="sm">What to ship</Heading>
              </Card.Header>
              <Card.Body>
                <SimpleGrid columns={{ base: 1, md: 2 }} gap={6}>
                  <Box>
                    <Text fontWeight="medium" mb={1}>
                      TACACS+ logs
                    </Text>
                    <Text fontSize="sm" color="fg.muted" mb={3}>
                      One event per log line, sent within seconds by every node
                      from its own log files.
                    </Text>
                    <VStack align="stretch" gap={2}>
                      {TACACS_SOURCES.map(({ key, label, hint }) => (
                        <Checkbox
                          key={key}
                          checked={form[key]}
                          disabled={readOnly}
                          onCheckedChange={(e) => set(key, !!e.checked)}
                        >
                          {label}{" "}
                          <Text as="span" color="fg.muted" fontSize="sm">
                            — {hint}
                          </Text>
                        </Checkbox>
                      ))}
                    </VStack>
                  </Box>
                  <Box>
                    <Text fontWeight="medium" mb={1}>
                      Application
                    </Text>
                    <Text fontSize="sm" color="fg.muted" mb={3}>
                      Changes made in this UI and over MCP. Sent from the
                      primary, where they are recorded.
                    </Text>
                    <Checkbox
                      checked={form.ship_audit}
                      disabled={readOnly}
                      onCheckedChange={(e) => set("ship_audit", !!e.checked)}
                    >
                      Audit log{" "}
                      <Text as="span" color="fg.muted" fontSize="sm">
                        — create / update / delete / activate
                      </Text>
                    </Checkbox>
                  </Box>
                </SimpleGrid>
              </Card.Body>
            </Card.Root>

            <SimpleGrid columns={{ base: 1, lg: 2 }} gap={4}>
              <Card.Root variant="outline">
                <Card.Header pb={2}>
                  <Heading size="sm">Webhook (Splunk HEC)</Heading>
                  <Text fontSize="sm" color="fg.muted">
                    Events are POSTed in batches as newline-separated JSON.
                    Delivery is retried until the receiver accepts them.
                  </Text>
                </Card.Header>
                <Card.Body>
                  <VStack align="stretch" gap={4}>
                    <Field label="URL" helperText="Leave empty to disable.">
                      <Input
                        value={form.webhook_url}
                        placeholder="https://splunk.example.com:8088/services/collector/event"
                        onChange={(e) => set("webhook_url", e.target.value)}
                      />
                    </Field>
                    <Field
                      label="Token"
                      helperText={
                        config.webhook_token_is_set
                          ? "A token is set. Leave empty to keep it."
                          : "Sent as Authorization: Splunk <token>."
                      }
                    >
                      <HStack w="full">
                        <Input
                          type="password"
                          autoComplete="new-password"
                          value={form.webhook_token}
                          disabled={form.clear_token}
                          placeholder={
                            config.webhook_token_is_set ? "••••••••" : ""
                          }
                          onChange={(e) => set("webhook_token", e.target.value)}
                        />
                        {config.webhook_token_is_set && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() =>
                              setForm({
                                ...form,
                                clear_token: !form.clear_token,
                                webhook_token: "",
                              })
                            }
                          >
                            {form.clear_token ? "Keep token" : "Clear token"}
                          </Button>
                        )}
                      </HStack>
                    </Field>
                    <SwitchRow
                      label="Verify TLS certificate"
                      hint="Turn off only for a receiver with a self-signed certificate."
                      checked={form.webhook_verify_tls}
                      disabled={readOnly}
                      onChange={(v) => set("webhook_verify_tls", v)}
                    />
                  </VStack>
                </Card.Body>
              </Card.Root>

              <Card.Root variant="outline">
                <Card.Header pb={2}>
                  <Heading size="sm">Syslog (RFC 5424)</Heading>
                  <Text fontSize="sm" color="fg.muted">
                    One message per event; the hostname is the node name. Over
                    TCP each message ends with a newline.
                  </Text>
                </Card.Header>
                <Card.Body>
                  <VStack align="stretch" gap={4}>
                    <Field
                      label="Host"
                      helperText="Hostname or IP address. Leave empty to disable."
                    >
                      <Input
                        value={form.syslog_host}
                        placeholder="syslog.example.com"
                        onChange={(e) => set("syslog_host", e.target.value)}
                      />
                    </Field>
                    <HStack align="start" gap={4}>
                      <Field
                        label="Port"
                        invalid={portInvalid}
                        errorText="1–65535"
                      >
                        <Input
                          inputMode="numeric"
                          value={form.syslog_port}
                          onChange={(e) => set("syslog_port", e.target.value)}
                        />
                      </Field>
                      <Field label="Protocol">
                        <NativeSelect.Root>
                          <NativeSelect.Field
                            value={form.syslog_protocol}
                            onChange={(e) =>
                              set(
                                "syslog_protocol",
                                e.target.value === "tcp" ? "tcp" : "udp",
                              )
                            }
                          >
                            <option value="udp">UDP</option>
                            <option value="tcp">TCP</option>
                          </NativeSelect.Field>
                          <NativeSelect.Indicator />
                        </NativeSelect.Root>
                      </Field>
                    </HStack>
                    {form.syslog_protocol === "udp" && (
                      <Text fontSize="sm" color="fg.muted">
                        UDP gives no delivery confirmation: a test event reports
                        "sent" even when nothing listens.
                      </Text>
                    )}
                  </VStack>
                </Card.Body>
              </Card.Root>
            </SimpleGrid>

            <HStack gap={3}>
              <Button
                type="submit"
                colorPalette="teal"
                loading={save.isPending}
                disabled={readOnly || !dirty || portInvalid}
              >
                Save
              </Button>
              <Button
                variant="outline"
                loading={test.isPending}
                disabled={dirty || (!config.webhook_url && !config.syslog_host)}
                onClick={() => test.mutate()}
              >
                <FiSend /> Send test event
              </Button>
              {dirty && (
                <Text fontSize="sm" color="fg.muted">
                  Save first to test the new settings.
                </Text>
              )}
            </HStack>
          </VStack>
        </fieldset>
      </form>

      <Box mt={6}>
        <StatusCard />
      </Box>

      <Alert.Root status="neutral" mt={4} borderRadius="md">
        <Alert.Indicator />
        <Alert.Description>
          tac_plus-ng can also send its own UDP syslog (RFC 3164) from every
          node: TACACS NG Settings → Remote Syslog Destination. That is part of
          the generated config and is independent of this page.
        </Alert.Description>
      </Alert.Root>
    </Container>
  )
}
