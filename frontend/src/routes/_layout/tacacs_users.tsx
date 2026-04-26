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

import { TacacsUsersService } from "@/client"
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

const PER_PAGE = 10

function getTacacsUsersQueryOptions({
  page,
  search,
}: {
  page: number
  search?: string
}) {
  return {
    queryFn: () =>
      TacacsUsersService.readTacacsUsers({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["tacacs_users", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_users")({
  component: TacacsUsers,
  validateSearch: (search) => tacacs_usersSearchSchema.parse(search),
})

function TacacsUsersTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [localSearch, setLocalSearch] = useState(search ?? "")
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsUsersQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  useEffect(() => {
    setLocalSearch(search ?? "")
  }, [search])

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_users",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      navigate({
        to: "/tacacs_users",
        search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
      })
    }, 500)
  }

  const tacacs_users = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      <Flex mt={4} justifyContent="flex-end">
        <InputGroup maxW="sm">
          <Input
            type="text"
            placeholder="Search by username, group, description..."
            value={localSearch}
            onChange={handleSearchChange}
            size="sm"
          />
        </InputGroup>
      </Flex>
      {isLoading ? (
        <PendingTacacsUsers />
      ) : tacacs_users.length === 0 ? (
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
      ) : (
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

function TacacsUsers() {
  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        TACACS Users
      </Heading>
      <AddTacacsUser />
      <TacacsUsersTable />
    </Container>
  )
}
