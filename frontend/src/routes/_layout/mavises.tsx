import {
  Container,
  EmptyState,
  Flex,
  Heading,
  HStack,
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

import { MavisesService } from "@/client"
import { MavisActionsMenu } from "@/components/Common/MavisActionsMenu"
import AddMavis from "@/components/Mavises/AddMavis"
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

const PER_PAGE = 5

function getMavisesQueryOptions({
  page,
  search,
}: {
  page: number
  search?: string
}) {
  return {
    queryFn: () =>
      MavisesService.readMavises({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["mavises", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/mavises")({
  component: Mavises,
  validateSearch: (search) => mavisesSearchSchema.parse(search),
})

function MavisesTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [localSearch, setLocalSearch] = useState(search ?? "")
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getMavisesQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  useEffect(() => {
    setLocalSearch(search ?? "")
  }, [search])

  const setPage = (page: number) => {
    navigate({
      to: "/mavises",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      navigate({
        to: "/mavises",
        search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
      })
    }, 500)
  }

  const mavises = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      <Flex mt={4} justifyContent="flex-end">
        <InputGroup maxW="sm">
          <Input
            type="text"
            placeholder="Search by key, value..."
            value={localSearch}
            onChange={handleSearchChange}
            size="sm"
          />
        </InputGroup>
      </Flex>
      {isLoading ? (
        <PendingMavises />
      ) : mavises.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>You don't have any mavises yet</EmptyState.Title>
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

function Mavises() {
  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        Mavises Management
      </Heading>
      <HStack my={4}>
        <AddMavis />
        <PreviewMavis />
      </HStack>
      <MavisesTable />
    </Container>
  )
}
