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
import { FiPlus, FiSend } from "react-icons/fi"
import { z } from "zod"

import type { NotificationChannelPublic } from "@/client"
import { NotificationChannelsService } from "@/client"
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

const CHANNEL_COLORS: Record<string, string> = {
  telegram: "blue",
  slack: "purple",
  discord: "indigo",
  teams: "teal",
  webhook: "gray",
  gchat: "green",
  email: "orange",
}

const CONFIG_PLACEHOLDERS: Record<string, string> = {
  telegram: `{\n  "bot_token": "your-bot-token",\n  "chat_id": "-100123456789",\n  "topic_id": ""\n}`,
  slack: `{\n  "webhook_url": "https://hooks.slack.com/services/..."\n}`,
  discord: `{\n  "webhook_url": "https://discord.com/api/webhooks/..."\n}`,
  teams: `{\n  "webhook_url": "https://outlook.office.com/webhook/..."\n}`,
  webhook: `{\n  "webhook_url": "https://your-endpoint.com/hook",\n  "token": "optional-bearer-token"\n}`,
  gchat: `{\n  "webhook_url": "https://chat.googleapis.com/v1/spaces/.../messages?key=..."\n}`,
  email: `{\n  "smtp_host": "smtp.gmail.com",\n  "smtp_port": 587,\n  "smtp_user": "you@gmail.com",\n  "smtp_password": "app-password",\n  "from_email": "you@gmail.com",\n  "to_email": "alerts@example.com",\n  "tls": true\n}`,
}

interface QueryParams {
  page: number
  perPage: number
}

function getQueryOptions({ page, perPage }: QueryParams) {
  return {
    queryFn: () =>
      NotificationChannelsService.readNotificationChannels({
        skip: (page - 1) * perPage,
        limit: perPage,
      }),
    queryKey: ["notification_channels", { page, perPage }],
  }
}

export const Route = createFileRoute("/_layout/notification_channels")({
  component: NotificationChannelsPage,
  validateSearch: (search) => searchSchema.parse(search),
})

interface ChannelFormData {
  name: string
  channel_type: string
  config_json: string
  enabled: boolean
}

const defaultForm: ChannelFormData = {
  name: "",
  channel_type: "telegram",
  config_json: CONFIG_PLACEHOLDERS.telegram,
  enabled: true,
}

function ChannelDialog({
  channel,
  onClose,
}: {
  channel?: NotificationChannelPublic
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ChannelFormData>(
    channel
      ? {
          name: channel.name,
          channel_type: channel.channel_type,
          config_json: channel.config_json ?? "{}",
          enabled: channel.enabled ?? true,
        }
      : defaultForm,
  )

  const mutation = useMutation({
    mutationFn: channel
      ? () =>
          NotificationChannelsService.updateNotificationChannel({
            id: channel.id,
            requestBody: form,
          })
      : () =>
          NotificationChannelsService.createNotificationChannel({
            requestBody: form,
          }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification_channels"] })
      onClose()
    },
  })

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const t = e.target.value
    setForm((p) => ({ ...p, channel_type: t, config_json: CONFIG_PLACEHOLDERS[t] ?? "{}" }))
  }

  return (
    <Stack gap={3}>
      <Box>
        <Text fontSize="sm" mb={1}>Name</Text>
        <Input
          value={form.name}
          onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
          placeholder="My Telegram Channel"
        />
      </Box>
      <Box>
        <Text fontSize="sm" mb={1}>Channel Type</Text>
        <select
          style={{ width: "100%", padding: "6px", borderRadius: "6px", border: "1px solid #ccc" }}
          value={form.channel_type}
          onChange={handleTypeChange}
        >
          <option value="telegram">Telegram</option>
          <option value="slack">Slack</option>
          <option value="discord">Discord</option>
          <option value="teams">Microsoft Teams</option>
          <option value="gchat">Google Chat</option>
          <option value="email">Email (SMTP)</option>
          <option value="webhook">Generic Webhook</option>
        </select>
      </Box>
      <Box>
        <Text fontSize="sm" mb={1}>Configuration (JSON)</Text>
        <Textarea
          value={form.config_json}
          onChange={(e) => setForm((p) => ({ ...p, config_json: e.target.value }))}
          rows={6}
          fontFamily="mono"
          fontSize="xs"
        />
      </Box>
      <Flex align="center" gap={2}>
        <Switch.Root
          checked={form.enabled}
          onCheckedChange={(e) => setForm((p) => ({ ...p, enabled: e.checked }))}
        >
          <Switch.HiddenInput />
          <Switch.Control><Switch.Thumb /></Switch.Control>
        </Switch.Root>
        <Text fontSize="sm">Enabled</Text>
      </Flex>
      <Flex justify="flex-end" gap={2} pt={2}>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button colorPalette="blue" loading={mutation.isPending} onClick={() => mutation.mutate()}>
          {channel ? "Save" : "Create"}
        </Button>
      </Flex>
    </Stack>
  )
}

function TestButton({ channel }: { channel: NotificationChannelPublic }) {
  const [status, setStatus] = useState<"idle" | "ok" | "fail">("idle")
  const mutation = useMutation({
    mutationFn: () =>
      NotificationChannelsService.testNotificationChannel({ id: channel.id }),
    onSuccess: () => setStatus("ok"),
    onError: () => setStatus("fail"),
  })

  return (
    <Button
      size="xs"
      variant="ghost"
      colorPalette={status === "ok" ? "green" : status === "fail" ? "red" : "blue"}
      loading={mutation.isPending}
      onClick={() => { setStatus("idle"); mutation.mutate() }}
    >
      <FiSend /> {status === "ok" ? "Sent!" : status === "fail" ? "Failed" : "Test"}
    </Button>
  )
}

function DeleteChannelButton({ channel }: { channel: NotificationChannelPublic }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const mutation = useMutation({
    mutationFn: () => NotificationChannelsService.deleteNotificationChannel({ id: channel.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification_channels"] })
      setOpen(false)
    },
  })

  return (
    <DialogRoot open={open} onOpenChange={(e) => setOpen(e.open)}>
      <DialogTrigger asChild>
        <Button size="xs" variant="ghost" colorPalette="red">Delete</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Delete Channel</DialogTitle></DialogHeader>
        <DialogCloseTrigger />
        <DialogBody>
          <Text>Delete <strong>{channel.name}</strong>?</Text>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          <Button colorPalette="red" loading={mutation.isPending} onClick={() => mutation.mutate()}>Delete</Button>
        </DialogFooter>
      </DialogContent>
    </DialogRoot>
  )
}

function NotificationChannelsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)
  const [editChannel, setEditChannel] = useState<NotificationChannelPublic | null>(null)
  const [addOpen, setAddOpen] = useState(false)

  const { data, isLoading } = useQuery(getQueryOptions({ page, perPage }))
  const count = data?.count ?? 0

  if (isLoading) return <Text>Loading...</Text>

  return (
    <Box>
      <Flex mb={4} justify="space-between" align="center">
        <PageSizeSelect value={perPage} onChange={(v) => { setPerPage(v); navigate({ search: { page: 1 } }) }} />
        <DialogRoot open={addOpen} onOpenChange={(e) => setAddOpen(e.open)}>
          <DialogTrigger asChild>
            <Button colorPalette="blue" size="sm"><FiPlus /> Add Channel</Button>
          </DialogTrigger>
          <DialogContent maxW="xl">
            <DialogHeader><DialogTitle>Create Notification Channel</DialogTitle></DialogHeader>
            <DialogCloseTrigger />
            <DialogBody><ChannelDialog onClose={() => setAddOpen(false)} /></DialogBody>
          </DialogContent>
        </DialogRoot>
      </Flex>

      {count === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <VStack>
              <EmptyState.Indicator><FiSend /></EmptyState.Indicator>
              <EmptyState.Title>No channels configured</EmptyState.Title>
              <EmptyState.Description>Add a channel to receive alert notifications.</EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Name</Table.ColumnHeader>
                <Table.ColumnHeader>Type</Table.ColumnHeader>
                <Table.ColumnHeader>Enabled</Table.ColumnHeader>
                <Table.ColumnHeader>Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {data?.data.map((ch) => (
                <Table.Row key={ch.id}>
                  <Table.Cell fontWeight="medium">{ch.name}</Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={CHANNEL_COLORS[ch.channel_type] ?? "gray"}>
                      {ch.channel_type}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={ch.enabled ? "green" : "gray"}>
                      {ch.enabled ? "On" : "Off"}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>
                    <Flex gap={1}>
                      <TestButton channel={ch} />
                      <DialogRoot open={editChannel?.id === ch.id} onOpenChange={(e) => setEditChannel(e.open ? ch : null)}>
                        <DialogTrigger asChild>
                          <Button size="xs" variant="ghost">Edit</Button>
                        </DialogTrigger>
                        <DialogContent maxW="xl">
                          <DialogHeader><DialogTitle>Edit Channel</DialogTitle></DialogHeader>
                          <DialogCloseTrigger />
                          <DialogBody><ChannelDialog channel={ch} onClose={() => setEditChannel(null)} /></DialogBody>
                        </DialogContent>
                      </DialogRoot>
                      <DeleteChannelButton channel={ch} />
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

function NotificationChannelsPage() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12} pb={4}>Notification Channels</Heading>
      <Text color="fg.muted" mb={6}>Configure destinations for alert notifications (Telegram, Slack, Discord, Teams, or generic webhooks).</Text>
      <NotificationChannelsTable />
    </Container>
  )
}
