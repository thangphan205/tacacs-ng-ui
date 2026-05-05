import {
  Container,
  EmptyState,
  Flex,
  Heading,
  Table,
  VStack,
} from "@chakra-ui/react"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiSearch } from "react-icons/fi"
import { z } from "zod"

import { TacacsUsersService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { SearchBox } from "@/components/Common/SearchBox"
import { TacacsUserActionsMenu } from "@/components/Common/TacacsUserActionsMenu"
import PendingTacacsUsers from "@/components/Pending/PendingTacacsUsers"
import AddTacacsUser from "@/components/TacacsUsers/AddTacacsUser"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const tacacs_usersSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 10

function getTacacsUsersQueryOptions({
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
      TacacsUsersService.readTacacsUsers({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["tacacs_users", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_users")({
  component: TacacsUsers,
  validateSearch: (search) => tacacs_usersSearchSchema.parse(search),
})

function TacacsUsersTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsUsersQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_users",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const tacacs_users = data?.data ?? []
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
            <EmptyState.Title>No TACACS users found</EmptyState.Title>
            <EmptyState.Description>
              Add a new TACACS user to get started
            </EmptyState.Description>
          </VStack>
        </EmptyState.Content>
      </EmptyState.Root>
    )
  }

  return (
    <>
      <Table.Root size="sm" mt={2}>
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader w="sm">ID</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Username</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Password Type</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Member</Table.ColumnHeader>
            <Table.ColumnHeader>Description</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {tacacs_users?.map((tacacs_user) => (
            <Table.Row
              key={tacacs_user.id}
              opacity={isPlaceholderData ? 0.5 : 1}
            >
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
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/tacacs_users",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        TACACS Users
      </Heading>
      <Flex mt={4} align="center" justify="space-between">
        <AddTacacsUser />
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by username, group, description..."
        />
      </Flex>
      <TacacsUsersTable />
    </Container>
  )
}
