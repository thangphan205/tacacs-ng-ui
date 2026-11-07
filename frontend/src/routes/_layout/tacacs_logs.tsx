import {
  Button,
  Container,
  EmptyState,
  Flex,
  Heading,
  Table,
  Tabs,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import { FiEye, FiSearch } from "react-icons/fi"
import { z } from "zod"
import { TacacsLogsService } from "@/client"
import { FilterSelect } from "@/components/Common/FilterSelect"
import { ListToolbar } from "@/components/Common/ListToolbar"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { RefreshControl } from "@/components/Common/RefreshControl"
import { SearchBox } from "@/components/Common/SearchBox"
import { DownloadTacacsLogButton } from "@/components/TacacsLogs/DownloadTacacsLogButton"
import ShowTacacsLog from "@/components/TacacsLogs/ShowTacacsLog"
import TacacsLogEventsTable from "@/components/TacacsLogs/TacacsLogEventsTable"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"
import { formatDateTime } from "@/utils"

const LOG_FILE_TYPES = [
  "access",
  "authentication",
  "authorization",
  "accounting",
] as const

type LogFileType = (typeof LOG_FILE_TYPES)[number]

const FILE_TYPE_OPTIONS = LOG_FILE_TYPES.map((t) => ({ value: t, label: t }))

const tacacs_logsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
  type: z.enum(LOG_FILE_TYPES).optional().catch(undefined),
})

type TacacsLogsSearch = z.infer<typeof tacacs_logsSearchSchema>

const DEFAULT_PER_PAGE = 10

function getFilesQueryOptions({
  page,
  search,
  type,
  perPage,
}: TacacsLogsSearch & { perPage: number }) {
  return {
    queryFn: () =>
      TacacsLogsService.listLogFiles({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
        log_type: type,
      }),
    queryKey: ["tacacs_logs_files", { page, search, type, perPage }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_logs")({
  component: TacacsLogs,
  validateSearch: (search) => tacacs_logsSearchSchema.parse(search),
})

function FilesTab() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search, type } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isFetching, dataUpdatedAt, refetch } = useQuery({
    ...getFilesQueryOptions({ page, search, type, perPage }),
    placeholderData: (prevData) => prevData,
  })

  // Each control owns one key, so a text search and a type filter combine.
  const setFilter = (patch: { search?: string; type?: LogFileType }) => {
    navigate({
      to: "/tacacs_logs",
      search: (prev) => ({ ...prev, ...patch, page: 1 }),
    })
  }

  const setPage = (p: number) => {
    navigate({ to: "/tacacs_logs", search: (prev) => ({ ...prev, page: p }) })
  }

  const logs = data?.data ?? []
  const count = data?.count ?? 0

  if (isLoading) return null

  return (
    <>
      <ListToolbar mt={4}>
        <SearchBox
          initialValue={search}
          onSearch={(val) => setFilter({ search: val || undefined })}
          placeholder="Search by filename..."
        />
        <FilterSelect
          value={type}
          onChange={(val) =>
            setFilter({ type: val as LogFileType | undefined })
          }
          options={FILE_TYPE_OPTIONS}
          placeholder="All types"
          ariaLabel="Filter by log file type"
          width="200px"
        />
        <RefreshControl
          onRefresh={() => refetch()}
          isFetching={isFetching}
          dataUpdatedAt={dataUpdatedAt}
          ariaLabel="Refresh log files"
        />
      </ListToolbar>

      {logs.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>No log files found</EmptyState.Title>
              <EmptyState.Description>
                No TACACS+ log files match the current filter.
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size={{ base: "sm", md: "md" }} mt={2}>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Filename</Table.ColumnHeader>
                <Table.ColumnHeader>Created At</Table.ColumnHeader>
                <Table.ColumnHeader w="1%">Download</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {logs.map((log: any) => (
                <Table.Row key={log.id}>
                  <Table.Cell truncate maxW="sm" cursor="pointer">
                    <ShowTacacsLog tacacs_log={log}>
                      <Button colorPalette="green" size="sm">
                        <FiEye />
                        {log.filename}
                      </Button>
                    </ShowTacacsLog>
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {formatDateTime(log.created_at, {
                      hour12: false,
                    })}
                  </Table.Cell>
                  <Table.Cell textAlign="center">
                    <DownloadTacacsLogButton log={log} iconOnly />
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>

          <Flex justifyContent="space-between" align="center" mt={4}>
            <PageSizeSelect
              value={perPage}
              onChange={(n) => {
                setPerPage(n)
                setPage(1)
              }}
            />
            <PaginationRoot
              count={count}
              pageSize={perPage}
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
    </>
  )
}

function TacacsLogs() {
  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        TACACS+ Logs
      </Heading>
      <Tabs.Root defaultValue="events" mt={6}>
        <Tabs.List>
          <Tabs.Trigger value="events">Events</Tabs.Trigger>
          <Tabs.Trigger value="files">Files</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="events">
          <TacacsLogEventsTable />
        </Tabs.Content>
        <Tabs.Content value="files">
          <FilesTab />
        </Tabs.Content>
      </Tabs.Root>
    </Container>
  )
}
