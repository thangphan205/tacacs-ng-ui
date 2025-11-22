import {
  Container,
  EmptyState,
  Flex,
  Heading,
  Table,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiSearch } from "react-icons/fi"
import { z } from "zod"

import { TacacsGroupsService } from "@/client"
import { TacacsGroupActionsMenu } from "@/components/Common/TacacsGroupActionsMenu"
import AddTacacsGroup from "@/components/TacacsGroups/AddTacacsGroup"
import PendingTacacsGroups from "@/components/Pending/PendingTacacsGroups"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const tacacs_groupsSearchSchema = z.object({
  page: z.number().catch(1),
})

const PER_PAGE = 5

function getTacacsGroupsQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      TacacsGroupsService.readTacacsGroups({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["tacacs_groups", { page }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_groups")({
  component: TacacsGroups,
  validateSearch: (search) => tacacs_groupsSearchSchema.parse(search),
})

function TacacsGroupsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsGroupsQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_groups",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const tacacs_groups = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  if (isLoading) {
    return <PendingTacacsGroups />
  }

  if (tacacs_groups.length === 0) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSearch />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>You don't have any tacacs_groups yet</EmptyState.Title>
            <EmptyState.Description>
              Add a new tacacs_group to get started
            </EmptyState.Description>
          </VStack>
        </EmptyState.Content>
      </EmptyState.Root>
    )
  }

  return (
    <>
      <Table.Root size={{ base: "sm", md: "md" }}>
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
            <Table.Row key={tacacs_group.id} opacity={isPlaceholderData ? 0.5 : 1}>
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
  )
}

function TacacsGroups() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
        TacacsGroups Management
      </Heading>
      <AddTacacsGroup />
      <TacacsGroupsTable />
    </Container>
  )
}
