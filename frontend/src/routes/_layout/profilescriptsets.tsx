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

import { ProfilescriptsetsService } from "@/client"
import { ProfileScriptSetActionsMenu } from "@/components/Common/ProfileScriptSetActionsMenu"
import { SearchBox } from "@/components/Common/SearchBox"
import PendingProfileScriptSets from "@/components/Pending/PendingProfileScriptSets"
import AddProfileScriptSet from "@/components/ProfileScriptSets/AddProfileScriptSet"
import PreviewProfile from "@/components/Profiles/PreviewProfile"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const profilescriptsetsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const PER_PAGE = 5

function getProfileScriptSetsQueryOptions({
  page,
  search,
}: {
  page: number
  search?: string
}) {
  return {
    queryFn: () =>
      ProfilescriptsetsService.readProfilescriptsets({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["profilescriptsets", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/profilescriptsets")({
  component: ProfileScriptSets,
  validateSearch: (search) => profilescriptsetsSearchSchema.parse(search),
})

function ProfileScriptSetsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getProfileScriptSetsQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/profilescriptsets",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const profilescriptsets = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      {isLoading ? (
        <PendingProfileScriptSets />
      ) : profilescriptsets.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>
                You don't have any profilescriptsets yet
              </EmptyState.Title>
              <EmptyState.Description>
                Add a new profilescriptset to get started
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size={{ base: "sm", md: "md" }} mt={2}>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader w="sm">ID</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Profile</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">
                  Profile Script Condition
                </Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Set Key</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Set Value</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {profilescriptsets?.map((profilescriptset) => (
                <Table.Row
                  key={profilescriptset.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell truncate maxW="sm">
                    {profilescriptset.id}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {profilescriptset.profile_name}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {profilescriptset.profilescript_block}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {profilescriptset.key}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {profilescriptset.value}
                  </Table.Cell>
                  <Table.Cell
                    color={!profilescriptset.description ? "gray" : "inherit"}
                    truncate
                    maxW="30%"
                  >
                    {profilescriptset.description || "N/A"}
                  </Table.Cell>
                  <Table.Cell>
                    <ProfileScriptSetActionsMenu
                      profilescriptset={profilescriptset}
                    />
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

function ProfileScriptSets() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/profilescriptsets",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        ProfileScriptSets Management
      </Heading>
      <Flex mt={4} align="center" justify="space-between">
        <Flex gap={2}>
          <AddProfileScriptSet />
          <PreviewProfile />
        </Flex>
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by key, value, description..."
        />
      </Flex>
      <ProfileScriptSetsTable />
    </Container>
  )
}
