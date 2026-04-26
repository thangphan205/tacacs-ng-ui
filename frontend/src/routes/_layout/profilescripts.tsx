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

import { ProfilescriptsService } from "@/client"
import { ProfileScriptActionsMenu } from "@/components/Common/ProfileScriptActionsMenu"
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

const PER_PAGE = 5

function getProfileScriptsQueryOptions({
  page,
  search,
}: {
  page: number
  search?: string
}) {
  return {
    queryFn: () =>
      ProfilescriptsService.readProfilescripts({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["profilescripts", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/profilescripts")({
  component: ProfileScripts,
  validateSearch: (search) => profilescriptsSearchSchema.parse(search),
})

function ProfileScriptsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [localSearch, setLocalSearch] = useState(search ?? "")
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getProfileScriptsQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  useEffect(() => {
    setLocalSearch(search ?? "")
  }, [search])

  const setPage = (page: number) => {
    navigate({
      to: "/profilescripts",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      navigate({
        to: "/profilescripts",
        search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
      })
    }, 500)
  }

  const profilescripts = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      <Flex mt={4} justifyContent="flex-end">
        <InputGroup maxW="sm">
          <Input
            type="text"
            placeholder="Search by condition, key, value, description..."
            value={localSearch}
            onChange={handleSearchChange}
            size="sm"
          />
        </InputGroup>
      </Flex>
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
          <Table.Root size={{ base: "sm", md: "md" }} mt={2}>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader w="sm">ID</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Profile Name</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Condition</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Key</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Value</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Action</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {profilescripts?.map((profilescript) => (
                <Table.Row
                  key={profilescript.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell truncate maxW="sm">
                    {profilescript.id}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {profilescript.profile_name}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {profilescript.condition}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {profilescript.key}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {profilescript.value}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {profilescript.action}
                  </Table.Cell>
                  <Table.Cell
                    color={!profilescript.description ? "gray" : "inherit"}
                    truncate
                    maxW="30%"
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

function ProfileScripts() {
  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        ProfileScripts Management
      </Heading>
      <Flex gap={2}>
        <AddProfileScript />
        <PreviewProfile />
      </Flex>
      <ProfileScriptsTable />
    </Container>
  )
}
