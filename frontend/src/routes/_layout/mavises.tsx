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
import { useState } from "react"
import { FiSearch } from "react-icons/fi"
import { z } from "zod"

import { MavisesService } from "@/client"
import { MavisActionsMenu } from "@/components/Common/MavisActionsMenu"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { SearchBox } from "@/components/Common/SearchBox"
import AddMavis from "@/components/Mavises/AddMavis"
import LoadMavisTemplate from "@/components/Mavises/LoadMavisTemplate"
import PreviewMavis from "@/components/Mavises/PreviewMavis"
import PendingMavises from "@/components/Pending/PendingMavises"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const mavisesSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 5

function getMavisesQueryOptions({
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
      MavisesService.readMavises({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["mavises", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/mavises")({
  component: Mavises,
  validateSearch: (search) => mavisesSearchSchema.parse(search),
})

function MavisesTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getMavisesQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/mavises",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const mavises = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      {isLoading ? (
        <PendingMavises />
      ) : mavises.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>
                You don't have any mavises yet
              </EmptyState.Title>
              <EmptyState.Description>
                Add a new mavis to get started
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
                <Table.ColumnHeader w="sm">Key</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Value</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {mavises?.map((mavis) => (
                <Table.Row key={mavis.id} opacity={isPlaceholderData ? 0.5 : 1}>
                  <Table.Cell truncate maxW="sm">
                    {mavis.id}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {mavis.mavis_key}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {mavis.mavis_value}
                  </Table.Cell>
                  <Table.Cell>
                    <MavisActionsMenu mavis={mavis} />
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

function Mavises() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/mavises",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        Mavises Management
      </Heading>
      <Flex mt={4} align="center" justify="space-between">
        <Flex gap={2}>
          <AddMavis />
          <LoadMavisTemplate />
          <PreviewMavis />
        </Flex>
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by key, value..."
        />
      </Flex>
      <MavisesTable />
    </Container>
  )
}
