import {
  Badge,
  Box,
  Container,
  EmptyState,
  Flex,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import { FiSearch, FiUser, FiUsers } from "react-icons/fi"
import { z } from "zod"

import { TacacsUsersService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { SearchBox } from "@/components/Common/SearchBox"
import { TacacsUserActionsMenu } from "@/components/Common/TacacsUserActionsMenu"
import PendingTacacsUsers from "@/components/Pending/PendingTacacsUsers"
import AddTacacsUser from "@/components/TacacsUsers/AddTacacsUser"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPageText,
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
      <Box
        borderWidth="1px"
        borderRadius="xl"
        overflow="hidden"
        bg="bg.panel"
        mt={6}
        shadow="sm"
      >
        <Table.Root
          size={{ base: "sm", md: "md" }}
          tableLayout="fixed"
          w="full"
        >
          <Table.Header bg="bg.muted">
            <Table.Row>
              <Table.ColumnHeader w="18%">Username</Table.ColumnHeader>
              <Table.ColumnHeader w="12%">Password Type</Table.ColumnHeader>
              <Table.ColumnHeader w="20%">Group Membership</Table.ColumnHeader>
              <Table.ColumnHeader w="12%">Generate</Table.ColumnHeader>
              <Table.ColumnHeader w="18%">Description</Table.ColumnHeader>
              <Table.ColumnHeader w="12%">Last Updated</Table.ColumnHeader>
              <Table.ColumnHeader w="8%">Actions</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {tacacs_users?.map((tacacs_user) => (
              <Table.Row
                key={tacacs_user.id}
                opacity={isPlaceholderData ? 0.5 : 1}
                _hover={{ bg: "bg.muted/50" }}
                transition="background 0.2s"
              >
                <Table.Cell fontWeight="medium" truncate>
                  <Flex align="center" gap={2} truncate>
                    <FiUser style={{ flexShrink: 0, color: "gray" }} />
                    <Text as="span" truncate>
                      {tacacs_user.username}
                    </Text>
                  </Flex>
                </Table.Cell>
                <Table.Cell>
                  <Badge
                    variant="subtle"
                    colorPalette={
                      tacacs_user.password_type === "crypt"
                        ? "green"
                        : tacacs_user.password_type === "mavis"
                          ? "blue"
                          : "orange"
                    }
                  >
                    {tacacs_user.password_type}
                  </Badge>
                </Table.Cell>
                <Table.Cell>
                  {tacacs_user.member ? (
                    <Flex gap={1} wrap="wrap">
                      {tacacs_user.member.split(",").map((group) => (
                        <Badge
                          key={group}
                          variant="outline"
                          colorPalette="purple"
                          size="sm"
                        >
                          {group}
                        </Badge>
                      ))}
                    </Flex>
                  ) : (
                    <Text color="fg.muted">—</Text>
                  )}
                </Table.Cell>
                <Table.Cell>
                  <Badge
                    colorPalette={tacacs_user.generate_config ? "green" : "red"}
                    variant="subtle"
                    size="sm"
                  >
                    {tacacs_user.generate_config ? "Yes" : "No"}
                  </Badge>
                </Table.Cell>
                <Table.Cell
                  color={!tacacs_user.description ? "gray" : "inherit"}
                  truncate
                >
                  {tacacs_user.description || "N/A"}
                </Table.Cell>
                <Table.Cell fontSize="sm" color="fg.muted">
                  {new Date(tacacs_user.updated_at).toLocaleString("en-US", {
                    hour12: false,
                  })}
                </Table.Cell>
                <Table.Cell>
                  <TacacsUserActionsMenu tacacs_user={tacacs_user} />
                </Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      </Box>
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
            <PaginationPageText format="long" color="fg.muted" fontSize="sm" />
            <Flex>
              <PaginationPrevTrigger />
              <PaginationItems />
              <PaginationNextTrigger />
            </Flex>
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
      <PageHeader
        title="TACACS Users"
        description="Configure local users, their authentication mechanisms (crypt, mavis, clear), and associate them with group permissions."
        icon={FiUsers}
      />
      <Flex mt={6} align="center" justify="space-between" gap={4} wrap="wrap">
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
