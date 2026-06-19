import {
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
import { FiLayers, FiSearch } from "react-icons/fi"
import { z } from "zod"

import { TacacsServicesService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { SearchBox } from "@/components/Common/SearchBox"
import { TacacsServiceActionsMenu } from "@/components/Common/TacacsServiceActionsMenu"
import PendingTacacsServices from "@/components/Pending/PendingTacacsServices"
import AddTacacsService from "@/components/TacacsServices/AddTacacsService"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPageText,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const tacacs_serviceSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 5

function getTacacsServicesQueryOptions({
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
      TacacsServicesService.readTacacsServices({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["tacacs_services", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_services")({
  component: TacacsServices,
  validateSearch: (search) => tacacs_serviceSearchSchema.parse(search),
})

function TacacsServicesTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsServicesQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_services",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const tacacs_service = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
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
          <Table.Root
            size={{ base: "sm", md: "md" }}
            mt={2}
            tableLayout="fixed"
            w="full"
          >
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader w="35%">Service Name</Table.ColumnHeader>
                <Table.ColumnHeader w="40%">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="17%">Last Updated</Table.ColumnHeader>
                <Table.ColumnHeader w="8%">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {tacacs_service?.map((tacacs_service) => (
                <Table.Row
                  key={tacacs_service.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell fontWeight="medium" truncate>
                    <Flex align="center" gap={2} truncate>
                      <FiLayers style={{ flexShrink: 0, color: "gray" }} />
                      <Text as="span" truncate>
                        {tacacs_service.name}
                      </Text>
                    </Flex>
                  </Table.Cell>
                  <Table.Cell
                    color={!tacacs_service.description ? "gray" : "inherit"}
                    truncate
                  >
                    {tacacs_service.description || "N/A"}
                  </Table.Cell>
                  <Table.Cell fontSize="sm" color="fg.muted">
                    {new Date(tacacs_service.updated_at).toLocaleString(
                      undefined,
                      {
                        hour12: false,
                      },
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    <TacacsServiceActionsMenu tacacs_service={tacacs_service} />
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
              <Flex align="center" gap={4}>
                <PaginationPageText
                  format="long"
                  color="fg.muted"
                  fontSize="sm"
                />
                <Flex>
                  <PaginationPrevTrigger />
                  <PaginationItems />
                  <PaginationNextTrigger />
                </Flex>
              </Flex>
            </PaginationRoot>
          </Flex>
        </>
      )}
    </>
  )
}

function TacacsServices() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/tacacs_services",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        TacacsServices Management
      </Heading>
      <Flex mt={4} align="center" justify="space-between">
        <AddTacacsService />
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by service name, description..."
        />
      </Flex>
      <TacacsServicesTable />
    </Container>
  )
}
