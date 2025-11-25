import {
  Container,
  Button,
  Input,
  InputGroup,
  Select,
  EmptyState,
  Flex,
  Heading,
  Table,
  VStack,
  createListCollection,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiSearch, FiEye } from "react-icons/fi"
import { z } from "zod" // Keep z for schema validation

import { TacacsLogsService } from "@/client"
import ShowTacacsLog from "@/components/TacacsLogs/ShowTacacsLog"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"
import { useState, useEffect, useRef } from "react" // Add useEffect, useRef for debounce

interface TacacsLogsSearch {
  page: number
  search?: string
}

const tacacs_logsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const PER_PAGE = 5

function getTacacsLogsQueryOptions({ page, search }: TacacsLogsSearch) {
  return {
    queryFn: () =>
      TacacsLogsService.listLogFiles({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search: search,
      }),
    queryKey: ["tacacs_logs", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_logs")({
  component: TacacsLogs,
  validateSearch: (search) => tacacs_logsSearchSchema.parse(search),
})

function TacacsLogsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [localSearchInput, setLocalSearchInput] = useState(search || ""); // Local state for input field
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const { data, isLoading } = useQuery({
    ...getTacacsLogsQueryOptions({ page, search: search }), // Use search from URL
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_logs",
      search: (prev) => ({ ...prev, page, search }),
    })
  }


  // Effect to update local input when URL search changes (e.g., back button)
  useEffect(() => {
    setLocalSearchInput(search || "");
  }, [search]);

  const handleSearchInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newSearchValue = event.target.value;
    setLocalSearchInput(newSearchValue);

    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
    }

    debounceTimeoutRef.current = setTimeout(() => {
      navigate({
        to: "/tacacs_logs",
        search: (prev) => ({
          ...prev,
          page: 1, // Reset page when search changes
          search: newSearchValue === "" ? undefined : newSearchValue,
        }),
      });
    }, 500); // 500ms debounce
  };

  const tacacs_logs = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  // console.log(searchString); // Remove this
  if (isLoading) {
    return null
  }
  const items_file_type = createListCollection<{ value: string; label: string }>({
    items: [
      { value: '', label: 'All Types' }, // Add an option to clear the filter
      { value: 'access', label: 'access' },
      { value: 'authentication', label: 'authentication' },
      { value: 'accounting', label: 'accounting' },
    ],
  });
  if (tacacs_logs.length === 0) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <Flex mb={4} width="100%" justifyContent="flex-end">
            {/* Search Input */}
            <InputGroup maxW="sm" mr={4}>
              <Input
                type="text"
                placeholder="Search logs..."
                value={localSearchInput}
                onChange={handleSearchInputChange}
                size="sm"
              />
            </InputGroup>

            {/* File Type Select */}
            <Select.Root
              collection={items_file_type}
              onSelect={(selection) => {
                navigate({
                  to: "/tacacs_logs",
                  search: (prev) => ({ ...prev, page: 1, search: selection.value === "" ? undefined : selection.value }),
                });
              }}
              size="sm"
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
                    {items_file_type.items.map((item) => (
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
          <EmptyState.Indicator>
            <FiSearch />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>You don't have any tacacs_logs yet</EmptyState.Title>
            <EmptyState.Description>
              Add a new tacacs_log to get started
            </EmptyState.Description>
          </VStack>
        </EmptyState.Content>
      </EmptyState.Root>
    )
  }

  return (
    <>
      <Flex mt={4} justifyContent="flex-end"> {/* Align items to the right */}
        {/* Search Input */}
        <InputGroup maxW="sm" mr={4}>
          <Input
            type="text"
            placeholder="Search logs..."
            value={localSearchInput}
            onChange={handleSearchInputChange}
            size="sm"
          />
        </InputGroup>

        {/* File Type Select */}
        <Select.Root
          collection={items_file_type}
          onSelect={(selection) => {
            navigate({
              to: "/tacacs_logs",
              search: (prev) => ({ ...prev, page: 1, search: selection.value === "" ? undefined : selection.value }),
            });
          }}
          size="sm"
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
                {items_file_type.items.map((item) => (
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
      <Table.Root size={{ base: "sm", md: "md" }}>
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader w="sm">ID</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Filename</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Created At</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {tacacs_logs?.map((tacacs_log: any) => (
            <Table.Row key={tacacs_log.id}>
              <Table.Cell truncate maxW="sm">
                {tacacs_log.id}
              </Table.Cell>
              <Table.Cell truncate maxW="sm" cursor="pointer">
                <ShowTacacsLog tacacs_log={tacacs_log}>
                  <Button colorPalette="green"><FiEye />{tacacs_log.filename}</Button>
                </ShowTacacsLog>
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {new Date(tacacs_log.created_at).toLocaleDateString()}
              </Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
      <Flex justifyContent="flex-end" mt={4}>
        <PaginationRoot
          count={count}
          pageSize={PER_PAGE}
          onPageChange={({ page }) => setPage(page)}
        >
          <Flex>
            <PaginationPrevTrigger />
            <PaginationItems />
            <PaginationNextTrigger />
          </Flex>
        </PaginationRoot>
      </Flex>
    </>
  )
}

function TacacsLogs() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
        TacacsLogs Management
      </Heading>
      <TacacsLogsTable />
    </Container>
  )
}
