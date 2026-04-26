import {
  Container,
  EmptyState,
  Flex,
  Heading,
  Input,
  InputGroup,
  Table,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect, useRef, useState } from "react"
import { FiSearch } from "react-icons/fi"
import { z } from "zod"

import { TacacsGroupsService } from "@/client"
import { TacacsGroupActionsMenu } from "@/components/Common/TacacsGroupActionsMenu"
import PendingTacacsGroups from "@/components/Pending/PendingTacacsGroups"
import AddTacacsGroup from "@/components/TacacsGroups/AddTacacsGroup"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const tacacs_groupsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const PER_PAGE = 10

function getTacacsGroupsQueryOptions({
  page,
  search,
}: {
  page: number
  search?: string
}) {
  return {
    queryFn: () =>
      TacacsGroupsService.readTacacsGroups({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["tacacs_groups", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_groups")({
  component: TacacsGroups,
  validateSearch: (search) => tacacs_groupsSearchSchema.parse(search),
})

function TacacsGroupsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [localSearch, setLocalSearch] = useState(search ?? "")
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsGroupsQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  useEffect(() => {
    setLocalSearch(search ?? "")
  }, [search])

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_groups",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      navigate({
        to: "/tacacs_groups",
        search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
      })
    }, 500)
  }

  const tacacs_groups = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      <Flex mt={4} justifyContent="flex-end">
        <InputGroup maxW="sm">
          <Input
            type="text"
            placeholder="Search by group name, description..."
            value={localSearch}
            onChange={handleSearchChange}
            size="sm"
          />
        </InputGroup>
      </Flex>
      {isLoading ? (
        <PendingTacacsGroups />
      ) : tacacs_groups.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>No TACACS groups found</EmptyState.Title>
              <EmptyState.Description>
                Add a new TACACS group to get started
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size="sm" mt={2}>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader w="sm">ID</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Group Name</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {tacacs_groups?.map((tacacs_group) => (
                <Table.Row
                  key={tacacs_group.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell truncate maxW="sm">
                    {tacacs_group.id}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {tacacs_group.group_name}
                  </Table.Cell>
                  <Table.Cell
                    color={!tacacs_group.description ? "gray" : "inherit"}
                    truncate
                    maxW="30%"
                  >
                    {tacacs_group.description || "N/A"}
                  </Table.Cell>
                  <Table.Cell>
                    <TacacsGroupActionsMenu tacacs_group={tacacs_group} />
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
      )}
    </>
  )
}

function TacacsGroups() {
  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        TACACS Groups
      </Heading>
      <AddTacacsGroup />
      <TacacsGroupsTable />
    </Container>
  )
}
