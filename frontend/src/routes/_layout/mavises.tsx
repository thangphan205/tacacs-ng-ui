import {
  Container,
  EmptyState,
  HStack,
  Flex,
  Heading,
  Table,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
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
})

const PER_PAGE = 5

function getMavisesQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      MavisesService.readMavises({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["mavises", { page }],
  }
}

export const Route = createFileRoute("/_layout/mavises")({
  component: Mavises,
  validateSearch: (search) => mavisesSearchSchema.parse(search),
})

function MavisesTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getMavisesQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/mavises",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const mavises = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  if (isLoading) {
    return <PendingMavises />
  }

  if (mavises.length === 0) {
    return (
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
    )
  }

  return (
    <>
      <Table.Root size={{ base: "sm", md: "md" }}>
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
  )
}

function Mavises() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
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
