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

import { TacacsServicesService } from "@/client"
import { TacacsServiceActionsMenu } from "@/components/Common/TacacsServiceActionsMenu"
import PendingTacacsServices from "@/components/Pending/PendingTacacsServices"
import AddTacacsService from "@/components/TacacsServices/AddTacacsService"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const tacacs_serviceSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const PER_PAGE = 5

function getTacacsServicesQueryOptions({
  page,
  search,
}: {
  page: number
  search?: string
}) {
  return {
    queryFn: () =>
      TacacsServicesService.readTacacsServices({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["tacacs_services", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_services")({
  component: TacacsServices,
  validateSearch: (search) => tacacs_serviceSearchSchema.parse(search),
})

function TacacsServicesTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [localSearch, setLocalSearch] = useState(search ?? "")
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsServicesQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  useEffect(() => {
    setLocalSearch(search ?? "")
  }, [search])

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_services",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      navigate({
        to: "/tacacs_services",
        search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
      })
    }, 500)
  }

  const tacacs_service = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      <Flex mt={4} justifyContent="flex-end">
        <InputGroup maxW="sm">
          <Input
            type="text"
            placeholder="Search by service name, description..."
            value={localSearch}
            onChange={handleSearchChange}
            size="sm"
          />
        </InputGroup>
      </Flex>
      {isLoading ? (
        <PendingTacacsServices />
      ) : tacacs_service.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>
                You don't have any tacacs_service yet
              </EmptyState.Title>
              <EmptyState.Description>
                Add a new tacacs_service to get started
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
                <Table.ColumnHeader w="sm">Service</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {tacacs_service?.map((tacacs_service) => (
                <Table.Row
                  key={tacacs_service.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell truncate maxW="sm">
                    {tacacs_service.id}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {tacacs_service.name}
                  </Table.Cell>
                  <Table.Cell
                    color={!tacacs_service.description ? "gray" : "inherit"}
                    truncate
                    maxW="30%"
                  >
                    {tacacs_service.description || "N/A"}
                  </Table.Cell>
                  <Table.Cell>
                    <TacacsServiceActionsMenu tacacs_service={tacacs_service} />
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

function TacacsServices() {
  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        TacacsServices Management
      </Heading>
      <AddTacacsService />
      <TacacsServicesTable />
    </Container>
  )
}
