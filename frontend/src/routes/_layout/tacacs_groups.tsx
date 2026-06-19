import {
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
import { useState } from "react"
import { FiSearch, FiUsers } from "react-icons/fi"
import { z } from "zod"

import { TacacsGroupsService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { SearchBox } from "@/components/Common/SearchBox"
import { TacacsGroupActionsMenu } from "@/components/Common/TacacsGroupActionsMenu"
import PendingTacacsGroups from "@/components/Pending/PendingTacacsGroups"
import AddTacacsGroup from "@/components/TacacsGroups/AddTacacsGroup"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPageText,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const tacacs_groupsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 10

function getTacacsGroupsQueryOptions({
  page,
  search,
  perPage,
}: {
  page: number
  search?: string
  perPage: number
}) {
  return {
    queryFn: () =>
      TacacsGroupsService.readTacacsGroups({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["tacacs_groups", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_groups")({
  component: TacacsGroups,
  validateSearch: (search) => tacacs_groupsSearchSchema.parse(search),
})

function TacacsGroupsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsGroupsQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_groups",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const tacacs_groups = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
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
          <Table.Root
            size={{ base: "sm", md: "md" }}
            mt={2}
            tableLayout="fixed"
            w="full"
          >
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader w="35%">Group Name</Table.ColumnHeader>
                <Table.ColumnHeader w="40%">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="17%">Last Updated</Table.ColumnHeader>
                <Table.ColumnHeader w="8%">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {tacacs_groups?.map((tacacs_group) => (
                <Table.Row
                  key={tacacs_group.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell fontWeight="medium" truncate>
                    <Flex align="center" gap={2} truncate>
                      <FiUsers style={{ flexShrink: 0, color: "gray" }} />
                      <Text as="span" truncate>
                        {tacacs_group.group_name}
                      </Text>
                    </Flex>
                  </Table.Cell>
                  <Table.Cell
                    color={!tacacs_group.description ? "gray" : "inherit"}
                    truncate
                  >
                    {tacacs_group.description || "N/A"}
                  </Table.Cell>
                  <Table.Cell fontSize="sm" color="fg.muted">
                    {new Date(tacacs_group.updated_at).toLocaleString(
                      undefined,
                      {
                        hour12: false,
                      },
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    <TacacsGroupActionsMenu tacacs_group={tacacs_group} />
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
              onPageChange={({ page }) => setPage(page)}
            >
              <Flex align="center" gap={4}>
                <PaginationPageText
                  format="long"
                  color="fg.muted"
                  fontSize="sm"
                />
                <Flex>
                  <PaginationPrevTrigger />
                  <PaginationItems />
                  <PaginationNextTrigger />
                </Flex>
              </Flex>
            </PaginationRoot>
          </Flex>
        </>
      )}
    </>
  )
}

function TacacsGroups() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/tacacs_groups",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        TACACS Groups
      </Heading>
      <Flex mt={4} align="center" justify="space-between">
        <AddTacacsGroup />
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by group name, description..."
        />
      </Flex>
      <TacacsGroupsTable />
    </Container>
  )
}
