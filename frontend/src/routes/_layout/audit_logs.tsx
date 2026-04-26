import {
  Badge,
  Box,
  Button,
  Code,
  Container,
  EmptyState,
  Flex,
  Heading,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiEye, FiSearch } from "react-icons/fi"
import { z } from "zod"
import type { AuditLogPublic } from "@/client"
import { AuditLogsService } from "@/client"
import { SearchBox } from "@/components/Common/SearchBox"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
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

const PER_PAGE = 20

const auditLogsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

interface AuditLogsSearch {
  page: number
  search?: string
}

function getAuditLogsQueryOptions({ page, search }: AuditLogsSearch) {
  return {
    queryFn: () =>
      AuditLogsService.readAuditLogs({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["audit_logs", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/audit_logs")({
  component: AuditLogsPage,
  validateSearch: (search) => auditLogsSearchSchema.parse(search),
})

const ACTION_COLORS: Record<string, string> = {
  CREATE: "green",
  UPDATE: "blue",
  DELETE: "red",
  LOGIN_SUCCESS: "teal",
  LOGIN_FAILED: "orange",
}

function formatJson(raw: string | null | undefined): string {
  if (!raw) return ""
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

function ValuesDialog({ log }: { log: AuditLogPublic }) {
  const hasValues = log.new_values || log.old_values
  if (!hasValues) return null

  return (
    <DialogRoot size="lg">
      <DialogTrigger asChild>
        <Button size="xs" variant="ghost" colorPalette="blue">
          <FiEye />
          Details
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {log.action} — {log.entity_type}
            {log.entity_id ? (
              <Text
                as="span"
                fontSize="sm"
                fontWeight="normal"
                ml={2}
                color="fg.muted"
              >
                {log.entity_id}
              </Text>
            ) : null}
          </DialogTitle>
        </DialogHeader>
        <DialogCloseTrigger />
        <DialogBody pb={6}>
          {log.old_values && (
            <Box mb={4}>
              <Text fontWeight="semibold" mb={1} color="red.500">
                Before
              </Text>
              <Code
                display="block"
                whiteSpace="pre"
                overflowX="auto"
                p={3}
                borderRadius="md"
                fontSize="xs"
              >
                {formatJson(log.old_values)}
              </Code>
            </Box>
          )}
          {log.new_values && (
            <Box>
              <Text fontWeight="semibold" mb={1} color="green.500">
                After
              </Text>
              <Code
                display="block"
                whiteSpace="pre"
                overflowX="auto"
                p={3}
                borderRadius="md"
                fontSize="xs"
              >
                {formatJson(log.new_values)}
              </Code>
            </Box>
          )}
        </DialogBody>
      </DialogContent>
    </DialogRoot>
  )
}

function AuditLogsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const { data, isLoading } = useQuery({
    ...getAuditLogsQueryOptions({ page, search }),
    placeholderData: (prev) => prev,
  })

  const setPage = (p: number) => {
    navigate({
      to: "/audit_logs",
      search: (prev) => ({ ...prev, page: p, search }),
    })
  }

  const logs = data?.data ?? []
  const count = data?.count ?? 0

  if (isLoading) return null

  return (
    <>
      {logs.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>No audit logs found</EmptyState.Title>
              <EmptyState.Description>
                User activity will appear here after actions are performed.
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size={{ base: "sm", md: "md" }} mt={2}>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Timestamp</Table.ColumnHeader>
                <Table.ColumnHeader>User</Table.ColumnHeader>
                <Table.ColumnHeader>Action</Table.ColumnHeader>
                <Table.ColumnHeader>Entity Type</Table.ColumnHeader>
                <Table.ColumnHeader>Entity ID</Table.ColumnHeader>
                <Table.ColumnHeader>Description</Table.ColumnHeader>
                <Table.ColumnHeader>IP Address</Table.ColumnHeader>
                <Table.ColumnHeader>Details</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {logs.map((log) => (
                <Table.Row key={log.id}>
                  <Table.Cell whiteSpace="nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </Table.Cell>
                  <Table.Cell truncate maxW="48">
                    {log.user_email}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      variant="solid"
                      colorPalette={ACTION_COLORS[log.action] ?? "gray"}
                    >
                      {log.action}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>{log.entity_type}</Table.Cell>
                  <Table.Cell
                    truncate
                    maxW="36"
                    fontSize="xs"
                    fontFamily="mono"
                  >
                    {log.entity_id ?? "—"}
                  </Table.Cell>
                  <Table.Cell truncate maxW="48">
                    {log.description ?? "—"}
                  </Table.Cell>
                  <Table.Cell>{log.ip_address ?? "—"}</Table.Cell>
                  <Table.Cell>
                    <ValuesDialog log={log} />
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
          <Flex justifyContent="flex-end" mt={4}>
            <PaginationRoot
              count={count}
              pageSize={PER_PAGE}
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
    </>
  )
}

function AuditLogsPage() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/audit_logs",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        Audit Logs
      </Heading>
      <Flex mt={4} justify="flex-end">
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by user, entity, action..."
        />
      </Flex>
      <AuditLogsTable />
    </Container>
  )
}
