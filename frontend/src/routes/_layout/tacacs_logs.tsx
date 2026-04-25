import {
  Button,
  Container,
  EmptyState,
  Flex,
  Heading,
  Input,
  InputGroup,
  Select,
  Table,
  Tabs,
  VStack,
  createListCollection,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect, useRef, useState } from "react"
import { FiEye, FiSearch } from "react-icons/fi"
import { z } from "zod"
import { TacacsLogsService } from "@/client"
import TacacsLogEventsTable from "@/components/TacacsLogs/TacacsLogEventsTable"
import ShowTacacsLog from "@/components/TacacsLogs/ShowTacacsLog"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"

interface TacacsLogsSearch {
  page: number
  search?: string
}

const tacacs_logsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const PER_PAGE = 20

const fileTypeCollection = createListCollection({
  items: [
    { value: "", label: "All Types" },
    { value: "access", label: "access" },
    { value: "authentication", label: "authentication" },
    { value: "authorization", label: "authorization" },
    { value: "accounting", label: "accounting" },
  ],
})

function getFilesQueryOptions({ page, search }: TacacsLogsSearch) {
  return {
    queryFn: () =>
      TacacsLogsService.listLogFiles({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search: search,
      }),
    queryKey: ["tacacs_logs_files", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_logs")({
  component: TacacsLogs,
  validateSearch: (search) => tacacs_logsSearchSchema.parse(search),
})

function FilesTab() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [localSearchInput, setLocalSearchInput] = useState(search || "")
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const { data, isLoading } = useQuery({
    ...getFilesQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  useEffect(() => {
    setLocalSearchInput(search || "")
  }, [search])

  const handleSearchInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearchInput(val)
    if (debounceTimeoutRef.current) clearTimeout(debounceTimeoutRef.current)
    debounceTimeoutRef.current = setTimeout(() => {
      navigate({
        to: "/tacacs_logs",
        search: (prev) => ({
          ...prev,
          page: 1,
          search: val === "" ? undefined : val,
        }),
      })
    }, 500)
  }

  const setPage = (p: number) => {
    navigate({ to: "/tacacs_logs", search: (prev) => ({ ...prev, page: p }) })
  }

  const logs = data?.data ?? []
  const count = data?.count ?? 0

  if (isLoading) return null

  return (
    <>
      <Flex mt={4} gap={3} justifyContent="flex-end">
        <InputGroup maxW="sm">
          <Input
            type="text"
            placeholder="Search logs..."
            value={localSearchInput}
            onChange={handleSearchInputChange}
            size="sm"
          />
        </InputGroup>

        <Select.Root
          collection={fileTypeCollection}
          onValueChange={({ value }) => {
            navigate({
              to: "/tacacs_logs",
              search: (prev) => ({
                ...prev,
                page: 1,
                search: value[0] === "" ? undefined : value[0],
              }),
            })
          }}
          size="sm"
          maxW="200px"
        >
          <Select.Control>
            <Select.Trigger>
              <Select.ValueText placeholder="Select file type" />
            </Select.Trigger>
            <Select.IndicatorGroup>
              <Select.ClearTrigger />
              <Select.Indicator />
            </Select.IndicatorGroup>
          </Select.Control>
          <Select.Positioner>
            <Select.Content>
              <Select.ItemGroup>
                {fileTypeCollection.items.map((item) => (
                  <Select.Item key={item.value} item={item.value}>
                    {item.label}
                    <Select.ItemIndicator />
                  </Select.Item>
                ))}
              </Select.ItemGroup>
            </Select.Content>
          </Select.Positioner>
        </Select.Root>
      </Flex>

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
                    {new Date(log.created_at).toLocaleDateString()}
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>

          <Flex justifyContent="flex-end" mt={4}>
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
    </>
  )
}

function TacacsLogs() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
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
