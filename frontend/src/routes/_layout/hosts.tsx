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

import { HostsService } from "@/client"
import { HostActionsMenu } from "@/components/Common/HostActionsMenu"
import AddHost from "@/components/Hosts/AddHost"
import PendingHosts from "@/components/Pending/PendingHosts"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const hostsSearchSchema = z.object({
  page: z.number().catch(1),
})

const PER_PAGE = 5

function getHostsQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      HostsService.readHosts({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["hosts", { page }],
  }
}

export const Route = createFileRoute("/_layout/hosts")({
  component: Hosts,
  validateSearch: (search) => hostsSearchSchema.parse(search),
})

function HostsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getHostsQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/hosts",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const hosts = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  if (isLoading) {
    return <PendingHosts />
  }

  if (hosts.length === 0) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSearch />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>You don't have any hosts yet</EmptyState.Title>
            <EmptyState.Description>
              Add a new host to get started
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
            <Table.ColumnHeader w="sm">Name</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Address</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Parent</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {hosts?.map((host) => (
            <Table.Row key={host.id} opacity={isPlaceholderData ? 0.5 : 1}>
              <Table.Cell truncate maxW="sm">
                {host.id}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {host.name}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {host.ipv4_address}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {host.parent || "None"}
              </Table.Cell>
              <Table.Cell
                color={!host.description ? "gray" : "inherit"}
                truncate
                maxW="30%"
              >
                {host.description || "N/A"}
              </Table.Cell>
              <Table.Cell>
                <HostActionsMenu host={host} />
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

function Hosts() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
        Hosts Management
      </Heading>
      <AddHost />
      <HostsTable />
    </Container>
  )
}
