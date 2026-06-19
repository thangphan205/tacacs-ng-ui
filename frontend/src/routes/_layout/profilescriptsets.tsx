import {
  Badge,
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
import { FiSearch } from "react-icons/fi"
import { z } from "zod"

import { ProfilescriptsetsService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
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

const DEFAULT_PER_PAGE = 5

function getProfileScriptSetsQueryOptions({
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
      ProfilescriptsetsService.readProfilescriptsets({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["profilescriptsets", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/profilescriptsets")({
  component: ProfileScriptSets,
  validateSearch: (search) => profilescriptsetsSearchSchema.parse(search),
})

function ProfileScriptSetsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getProfileScriptSetsQueryOptions({ page, search, perPage }),
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
          <Table.Root
            size={{ base: "sm", md: "md" }}
            mt={2}
            tableLayout="fixed"
            w="full"
          >
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader w="30%">
                  Profile / Condition
                </Table.ColumnHeader>
                <Table.ColumnHeader w="15%">Set Key</Table.ColumnHeader>
                <Table.ColumnHeader w="20%">Set Value</Table.ColumnHeader>
                <Table.ColumnHeader w="27%">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="8%">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {profilescriptsets?.map((profilescriptset) => (
                <Table.Row
                  key={profilescriptset.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell>
                    <Text fontWeight="medium" truncate>
                      {profilescriptset.profile_name}
                    </Text>
                    <Badge
                      variant="subtle"
                      colorPalette="teal"
                      mt={0.5}
                      fontSize="xs"
                    >
                      {profilescriptset.profilescript_block}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell truncate>{profilescriptset.key}</Table.Cell>
                  <Table.Cell truncate>{profilescriptset.value}</Table.Cell>
                  <Table.Cell
                    color={!profilescriptset.description ? "gray" : "inherit"}
                    truncate
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
