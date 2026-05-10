import {
  Badge,
  Box,
  Button,
  Container,
  EmptyState,
  Flex,
  Heading,
  Input,
  Stack,
  Switch,
  Table,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiBell, FiPlus, FiSearch } from "react-icons/fi"
import { z } from "zod"

import type { AlertRulePublic } from "@/client"
import { AlertRulesService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"

const DEFAULT_PER_PAGE = 10

const searchSchema = z.object({
  page: z.number().catch(1),
})

const SEVERITY_COLORS: Record<string, string> = {
  low: "blue",
  medium: "yellow",
  high: "orange",
  critical: "red",
}

interface QueryParams {
  page: number
  perPage: number
}

function getQueryOptions({ page, perPage }: QueryParams) {
  return {
    queryFn: () =>
      AlertRulesService.readAlertRules({
        skip: (page - 1) * perPage,
        limit: perPage,
      }),
    queryKey: ["alert_rules", { page, perPage }],
  }
}

export const Route = createFileRoute("/_layout/alert_rules")({
  component: AlertRulesPage,
  validateSearch: (search) => searchSchema.parse(search),
})

interface RuleFormData {
  name: string
  description: string
  log_type: string
  condition_field: string
  condition_operator: string
  threshold: string
  time_window_minutes: string
  severity: string
  cooldown_minutes: string
  enabled: boolean
}

const defaultForm: RuleFormData = {
  name: "",
  description: "",
  log_type: "auth",
  condition_field: "fail_count",
  condition_operator: "gt",
  threshold: "5",
  time_window_minutes: "10",
  severity: "medium",
  cooldown_minutes: "60",
  enabled: true,
}

function RuleDialog({
  rule,
  onClose,
}: {
  rule?: AlertRulePublic
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<RuleFormData>(
    rule
      ? {
          name: rule.name,
          description: rule.description ?? "",
          log_type: rule.log_type,
          condition_field: rule.condition_field,
          condition_operator: rule.condition_operator,
          threshold: String(rule.threshold ?? ""),
          time_window_minutes: String(rule.time_window_minutes),
          severity: rule.severity,
          cooldown_minutes: String(rule.cooldown_minutes),
          enabled: rule.enabled,
        }
      : defaultForm,
  )

  const mutation = useMutation({
    mutationFn: rule
      ? (data: typeof form) =>
          AlertRulesService.updateAlertRule({
            id: rule.id,
            requestBody: {
              name: data.name,
              description: data.description || undefined,
              log_type: data.log_type,
              condition_field: data.condition_field,
              condition_operator: data.condition_operator,
              threshold: data.threshold ? Number(data.threshold) : undefined,
              time_window_minutes: Number(data.time_window_minutes),
              severity: data.severity,
              cooldown_minutes: Number(data.cooldown_minutes),
              enabled: data.enabled,
            },
          })
      : (data: typeof form) =>
          AlertRulesService.createAlertRule({
            requestBody: {
              name: data.name,
              description: data.description || undefined,
              log_type: data.log_type,
              condition_field: data.condition_field,
              condition_operator: data.condition_operator,
              threshold: data.threshold ? Number(data.threshold) : undefined,
              time_window_minutes: Number(data.time_window_minutes),
              severity: data.severity,
              cooldown_minutes: Number(data.cooldown_minutes),
              enabled: data.enabled,
            },
          }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert_rules"] })
      onClose()
    },
  })

  const f = (k: keyof RuleFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm((prev) => ({ ...prev, [k]: e.target.value }))
  }

  return (
    <Stack gap={3}>
      <Box>
        <Text fontSize="sm" mb={1}>Name</Text>
        <Input value={form.name} onChange={f("name")} placeholder="High fail rate" />
      </Box>
      <Box>
        <Text fontSize="sm" mb={1}>Description</Text>
        <Textarea value={form.description} onChange={f("description")} rows={2} />
      </Box>
      <Flex gap={3}>
        <Box flex={1}>
          <Text fontSize="sm" mb={1}>Log Type</Text>
          <select style={{ width: "100%", padding: "6px", borderRadius: "6px", border: "1px solid #ccc" }} value={form.log_type} onChange={f("log_type")}>
            <option value="auth">Authentication</option>
            <option value="authz">Authorization</option>
            <option value="all">All</option>
          </select>
        </Box>
        <Box flex={1}>
          <Text fontSize="sm" mb={1}>Severity</Text>
          <select style={{ width: "100%", padding: "6px", borderRadius: "6px", border: "1px solid #ccc" }} value={form.severity} onChange={f("severity")}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </Box>
      </Flex>
      <Flex gap={3}>
        <Box flex={1}>
          <Text fontSize="sm" mb={1}>Condition Field</Text>
          <select style={{ width: "100%", padding: "6px", borderRadius: "6px", border: "1px solid #ccc" }} value={form.condition_field} onChange={f("condition_field")}>
            <option value="fail_count">Fail Count</option>
            <option value="deny_count">Deny Count</option>
            <option value="username">New Username</option>
            <option value="client_ip">New Source IP</option>
          </select>
        </Box>
        <Box flex={1}>
          <Text fontSize="sm" mb={1}>Operator</Text>
          <select style={{ width: "100%", padding: "6px", borderRadius: "6px", border: "1px solid #ccc" }} value={form.condition_operator} onChange={f("condition_operator")}>
            <option value="gt">Greater Than</option>
            <option value="lt">Less Than</option>
            <option value="eq">Equal To</option>
            <option value="new_value">New Value</option>
          </select>
        </Box>
        <Box flex={1}>
          <Text fontSize="sm" mb={1}>Threshold</Text>
          <Input value={form.threshold} onChange={f("threshold")} placeholder="5" type="number" />
        </Box>
      </Flex>
      <Flex gap={3}>
        <Box flex={1}>
          <Text fontSize="sm" mb={1}>Window (min)</Text>
          <Input value={form.time_window_minutes} onChange={f("time_window_minutes")} type="number" />
        </Box>
        <Box flex={1}>
          <Text fontSize="sm" mb={1}>Cooldown (min)</Text>
          <Input value={form.cooldown_minutes} onChange={f("cooldown_minutes")} type="number" />
        </Box>
      </Flex>
      <Flex align="center" gap={2}>
        <Switch.Root
          checked={form.enabled}
          onCheckedChange={(e) => setForm((p) => ({ ...p, enabled: e.checked }))}
        >
          <Switch.HiddenInput />
          <Switch.Control>
            <Switch.Thumb />
          </Switch.Control>
        </Switch.Root>
        <Text fontSize="sm">Enabled</Text>
      </Flex>
      <Flex justify="flex-end" gap={2} pt={2}>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button
          colorPalette="blue"
          loading={mutation.isPending}
          onClick={() => mutation.mutate(form)}
        >
          {rule ? "Save" : "Create"}
        </Button>
      </Flex>
    </Stack>
  )
}

function DeleteRuleButton({ rule }: { rule: AlertRulePublic }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const mutation = useMutation({
    mutationFn: () => AlertRulesService.deleteAlertRule({ id: rule.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alert_rules"] })
      setOpen(false)
    },
  })

  return (
    <DialogRoot open={open} onOpenChange={(e) => setOpen(e.open)}>
      <DialogTrigger asChild>
        <Button size="xs" variant="ghost" colorPalette="red">Delete</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Delete Alert Rule</DialogTitle></DialogHeader>
        <DialogCloseTrigger />
        <DialogBody>
          <Text>Delete <strong>{rule.name}</strong>? This will also remove all associated alert history.</Text>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button colorPalette="red" loading={mutation.isPending} onClick={() => mutation.mutate()}>Delete</Button>
        </DialogFooter>
      </DialogContent>
    </DialogRoot>
  )
}

function AlertRulesTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)
  const [editRule, setEditRule] = useState<AlertRulePublic | null>(null)
  const [addOpen, setAddOpen] = useState(false)

  const { data, isLoading } = useQuery(getQueryOptions({ page, perPage }))
  const count = data?.count ?? 0

  if (isLoading) return <Text>Loading...</Text>

  return (
    <Box>
      <Flex mb={4} justify="space-between" align="center">
        <Flex gap={2} align="center">
          <PageSizeSelect value={perPage} onChange={(v) => { setPerPage(v); navigate({ search: { page: 1 } }) }} />
        </Flex>
        <DialogRoot open={addOpen} onOpenChange={(e) => setAddOpen(e.open)}>
          <DialogTrigger asChild>
            <Button colorPalette="blue" size="sm"><FiPlus /> Add Rule</Button>
          </DialogTrigger>
          <DialogContent maxW="2xl">
            <DialogHeader><DialogTitle>Create Alert Rule</DialogTitle></DialogHeader>
            <DialogCloseTrigger />
            <DialogBody><RuleDialog onClose={() => setAddOpen(false)} /></DialogBody>
          </DialogContent>
        </DialogRoot>
      </Flex>

      {count === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <VStack>
              <EmptyState.Indicator><FiBell /></EmptyState.Indicator>
              <EmptyState.Title>No alert rules</EmptyState.Title>
              <EmptyState.Description>Create a rule to start receiving alerts.</EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Name</Table.ColumnHeader>
                <Table.ColumnHeader>Severity</Table.ColumnHeader>
                <Table.ColumnHeader>Log Type</Table.ColumnHeader>
                <Table.ColumnHeader>Condition</Table.ColumnHeader>
                <Table.ColumnHeader>Window</Table.ColumnHeader>
                <Table.ColumnHeader>Last Fired</Table.ColumnHeader>
                <Table.ColumnHeader>Enabled</Table.ColumnHeader>
                <Table.ColumnHeader>Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {data?.data.map((rule) => (
                <Table.Row key={rule.id}>
                  <Table.Cell fontWeight="medium">{rule.name}</Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={SEVERITY_COLORS[rule.severity] ?? "gray"}>
                      {rule.severity}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>{rule.log_type}</Table.Cell>
                  <Table.Cell fontSize="xs" color="fg.muted">
                    {rule.condition_field} {rule.condition_operator} {rule.threshold ?? "—"}
                  </Table.Cell>
                  <Table.Cell>{rule.time_window_minutes}m</Table.Cell>
                  <Table.Cell fontSize="xs" color="fg.muted">
                    {rule.last_fired_at ? new Date(rule.last_fired_at).toLocaleString() : "Never"}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={rule.enabled ? "green" : "gray"}>
                      {rule.enabled ? "On" : "Off"}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>
                    <Flex gap={1}>
                      <DialogRoot open={editRule?.id === rule.id} onOpenChange={(e) => setEditRule(e.open ? rule : null)}>
                        <DialogTrigger asChild>
                          <Button size="xs" variant="ghost">Edit</Button>
                        </DialogTrigger>
                        <DialogContent maxW="2xl">
                          <DialogHeader><DialogTitle>Edit Alert Rule</DialogTitle></DialogHeader>
                          <DialogCloseTrigger />
                          <DialogBody><RuleDialog rule={rule} onClose={() => setEditRule(null)} /></DialogBody>
                        </DialogContent>
                      </DialogRoot>
                      <DeleteRuleButton rule={rule} />
                    </Flex>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>

          <PaginationRoot
            count={count}
            pageSize={perPage}
            page={page}
            onPageChange={(e) => navigate({ search: { page: e.page } })}
          >
            <Flex mt={4} justify="center" gap={2}>
              <PaginationPrevTrigger />
              <PaginationItems />
              <PaginationNextTrigger />
            </Flex>
          </PaginationRoot>
        </>
      )}
    </Box>
  )
}

function AlertRulesPage() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12} pb={4}>Alert Rules</Heading>
      <Text color="fg.muted" mb={6}>Define conditions that trigger notifications when suspicious TACACS+ activity is detected.</Text>
      <AlertRulesTable />
    </Container>
  )
}
