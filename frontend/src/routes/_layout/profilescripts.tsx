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

import { ProfilescriptsService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { ProfileScriptActionsMenu } from "@/components/Common/ProfileScriptActionsMenu"
import { SearchBox } from "@/components/Common/SearchBox"
import PendingProfileScripts from "@/components/Pending/PendingProfileScripts"
import AddProfileScript from "@/components/ProfileScripts/AddProfileScript"
import PreviewProfile from "@/components/Profiles/PreviewProfile"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const profilescriptsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 5

function getProfileScriptsQueryOptions({
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
      ProfilescriptsService.readProfilescripts({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["profilescripts", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/profilescripts")({
  component: ProfileScripts,
  validateSearch: (search) => profilescriptsSearchSchema.parse(search),
})

function ProfileScriptsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getProfileScriptsQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/profilescripts",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const profilescripts = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      {isLoading ? (
        <PendingProfileScripts />
      ) : profilescripts.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>
                You don't have any profilescripts yet
              </EmptyState.Title>
              <EmptyState.Description>
                Add a new profilescript to get started
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
                <Table.ColumnHeader w="28%">
                  Profile / Condition
                </Table.ColumnHeader>
                <Table.ColumnHeader w="12%">Key</Table.ColumnHeader>
                <Table.ColumnHeader w="15%">Value</Table.ColumnHeader>
                <Table.ColumnHeader w="10%">Action</Table.ColumnHeader>
                <Table.ColumnHeader w="27%">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="8%">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {profilescripts?.map((profilescript) => (
                <Table.Row
                  key={profilescript.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell>
                    <Text fontWeight="medium" truncate>
                      {profilescript.profile_name}
                    </Text>
                    <Badge
                      variant="subtle"
                      colorPalette="teal"
                      mt={0.5}
                      fontSize="xs"
                    >
                      {profilescript.condition}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell truncate>{profilescript.key}</Table.Cell>
                  <Table.Cell truncate>{profilescript.value}</Table.Cell>
                  <Table.Cell truncate>{profilescript.action}</Table.Cell>
                  <Table.Cell
                    color={!profilescript.description ? "gray" : "inherit"}
                    truncate
                  >
                    {profilescript.description || "N/A"}
                  </Table.Cell>
                  <Table.Cell>
                    <ProfileScriptActionsMenu profilescript={profilescript} />
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

function ProfileScripts() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/profilescripts",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        ProfileScripts Management
      </Heading>
      <Flex mt={4} align="center" justify="space-between">
        <Flex gap={2}>
          <AddProfileScript />
          <PreviewProfile />
        </Flex>
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by condition, key, value, description..."
        />
      </Flex>
      <ProfileScriptsTable />
    </Container>
  )
}
