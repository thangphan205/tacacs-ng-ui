import {
  Badge,
  Box,
  Container,
  EmptyState,
  Flex,
  Heading,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiAlertCircle } from "react-icons/fi"
import { z } from "zod"

import { AlertEventsService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"
import { Table } from "@chakra-ui/react"

const DEFAULT_PER_PAGE = 20

const searchSchema = z.object({
  page: z.number().catch(1),
  status: z.string().optional(),
})

const SEVERITY_COLORS: Record<string, string> = {
  low: "blue",
  medium: "yellow",
  high: "orange",
  critical: "red",
}

const STATUS_COLORS: Record<string, string> = {
  sent: "green",
  failed: "red",
}

interface QueryParams {
  page: number
  perPage: number
  status?: string
}

function getQueryOptions({ page, perPage, status }: QueryParams) {
  return {
    queryFn: () =>
      AlertEventsService.readAlertEvents({
        skip: (page - 1) * perPage,
        limit: perPage,
        status: status ?? undefined,
      }),
    queryKey: ["alert_events", { page, perPage, status }],
  }
}

export const Route = createFileRoute("/_layout/alert_events")({
  component: AlertEventsPage,
  validateSearch: (search) => searchSchema.parse(search),
})

function AlertEventsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, status } = Route.useSearch()
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading } = useQuery(getQueryOptions({ page, perPage, status }))
  const count = data?.count ?? 0

  if (isLoading) return <Text>Loading...</Text>

  return (
    <Box>
      <Flex mb={4} gap={3} align="center">
        <PageSizeSelect value={perPage} onChange={(v) => { setPerPage(v); navigate({ search: (s) => ({ ...s, page: 1 }) }) }} />
        <select
          style={{ padding: "6px", borderRadius: "6px", border: "1px solid #ccc" }}
          value={status ?? ""}
          onChange={(e) => navigate({ search: (s) => ({ ...s, status: e.target.value || undefined, page: 1 }) })}
        >
          <option value="">All statuses</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
        </select>
      </Flex>

      {count === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <VStack>
              <EmptyState.Indicator><FiAlertCircle /></EmptyState.Indicator>
              <EmptyState.Title>No alert events</EmptyState.Title>
              <EmptyState.Description>Alerts will appear here when rules are triggered.</EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Triggered At</Table.ColumnHeader>
                <Table.ColumnHeader>Rule</Table.ColumnHeader>
                <Table.ColumnHeader>Severity</Table.ColumnHeader>
                <Table.ColumnHeader>Channel</Table.ColumnHeader>
                <Table.ColumnHeader>Status</Table.ColumnHeader>
                <Table.ColumnHeader>Error</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {data?.data.map((ev) => (
                <Table.Row key={ev.id}>
                  <Table.Cell fontSize="xs" whiteSpace="nowrap">
                    {new Date(ev.triggered_at).toLocaleString()}
                  </Table.Cell>
                  <Table.Cell fontWeight="medium">{ev.rule_name ?? ev.rule_id}</Table.Cell>
                  <Table.Cell>
                    {ev.rule_severity && (
                      <Badge colorPalette={SEVERITY_COLORS[ev.rule_severity] ?? "gray"}>
                        {ev.rule_severity}
                      </Badge>
                    )}
                  </Table.Cell>
                  <Table.Cell>{ev.channel_name ?? ev.channel_id}</Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={STATUS_COLORS[ev.status] ?? "gray"}>
                      {ev.status}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell fontSize="xs" color="fg.muted" maxW="200px">
                    <Text truncate>{ev.error_message ?? "—"}</Text>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>

          <PaginationRoot
            count={count}
            pageSize={perPage}
            page={page}
            onPageChange={(e) => navigate({ search: (s) => ({ ...s, page: e.page }) })}
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

function AlertEventsPage() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12} pb={4}>Alert History</Heading>
      <Text color="fg.muted" mb={6}>History of all triggered alerts and their delivery status.</Text>
      <AlertEventsTable />
    </Container>
  )
}
