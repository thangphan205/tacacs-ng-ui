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

import { TacacsUsersService } from "@/client"
import { TacacsUserActionsMenu } from "@/components/Common/TacacsUserActionsMenu"
import AddTacacsUser from "@/components/TacacsUsers/AddTacacsUser"
import PendingTacacsUsers from "@/components/Pending/PendingTacacsUsers"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const tacacs_usersSearchSchema = z.object({
  page: z.number().catch(1),
})

const PER_PAGE = 10

function getTacacsUsersQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      TacacsUsersService.readTacacsUsers({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["tacacs_users", { page }],
  }
}


export const Route = createFileRoute("/_layout/tacacs_users")({
  component: TacacsUsers,
  validateSearch: (search) => tacacs_usersSearchSchema.parse(search),
})

function TacacsUsersTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsUsersQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_users",
      search: (prev) => ({ ...prev, page }),
    })
  }


  const tacacs_users = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  if (isLoading) {
    return <PendingTacacsUsers />
  }

  if (tacacs_users.length === 0) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSearch />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>You don't have any tacacs_users yet</EmptyState.Title>
            <EmptyState.Description>
              Add a new tacacs_user to get started
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
            <Table.ColumnHeader w="sm">Username</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Password Type</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Member</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {tacacs_users?.map((tacacs_user) => (
            <Table.Row key={tacacs_user.id} opacity={isPlaceholderData ? 0.5 : 1}>
              <Table.Cell truncate maxW="sm">
                {tacacs_user.id}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {tacacs_user.username}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {tacacs_user.password_type}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {tacacs_user.member}
              </Table.Cell>
              <Table.Cell
                color={!tacacs_user.description ? "gray" : "inherit"}
                truncate
                maxW="30%"
              >
                {tacacs_user.description || "N/A"}
              </Table.Cell>
              <Table.Cell>
                <TacacsUserActionsMenu tacacs_user={tacacs_user} />
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

function TacacsUsers() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
        TacacsUsers Management
      </Heading>
      <AddTacacsUser />
      <TacacsUsersTable />
    </Container>
  )
}
