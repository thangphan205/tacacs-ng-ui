import {
  Badge,
  Box,
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
import { FiServer } from "react-icons/fi"
import { z } from "zod"

import { HostsService } from "@/client"
import { HostActionsMenu } from "@/components/Common/HostActionsMenu"
import { SearchBox } from "@/components/Common/SearchBox"
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
  search: z.string().optional(),
})

const PER_PAGE = 5

function getHostsQueryOptions({
  page,
  search,
}: {
  page: number
  search?: string
}) {
  return {
    queryFn: () =>
      HostsService.readHosts({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["hosts", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/hosts")({
  component: Hosts,
  validateSearch: (search) => hostsSearchSchema.parse(search),
})

function HostsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getHostsQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/hosts",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const hosts = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      {isLoading ? (
        <PendingHosts />
      ) : hosts.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiServer />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>No hosts configured</EmptyState.Title>
              <EmptyState.Description>
                Add your first network device to get started
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size={{ base: "sm", md: "md" }} mt={2}>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Name</Table.ColumnHeader>
                <Table.ColumnHeader>IPv4 Address</Table.ColumnHeader>
                <Table.ColumnHeader>IPv6 Address</Table.ColumnHeader>
                <Table.ColumnHeader>Parent</Table.ColumnHeader>
                <Table.ColumnHeader>Description</Table.ColumnHeader>
                <Table.ColumnHeader w="16">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {hosts.map((host) => (
                <Table.Row key={host.id} opacity={isPlaceholderData ? 0.5 : 1}>
                  <Table.Cell fontWeight="medium">{host.name}</Table.Cell>
                  <Table.Cell>
                    {host.ipv4_address ? (
                      <Badge colorPalette="blue" variant="outline" size="sm">
                        {host.ipv4_address}
                      </Badge>
                    ) : (
                      <Text color="fg.muted">—</Text>
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    {host.ipv6_address ? (
                      <Badge colorPalette="purple" variant="outline" size="sm">
                        {host.ipv6_address}
                      </Badge>
                    ) : (
                      <Text color="fg.muted">—</Text>
                    )}
                  </Table.Cell>
                  <Table.Cell color={!host.parent ? "fg.muted" : "inherit"}>
                    {host.parent || "—"}
                  </Table.Cell>
                  <Table.Cell
                    color={!host.description ? "fg.muted" : "inherit"}
                    truncate
                    maxW="xs"
                  >
                    {host.description || "—"}
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
      )}
    </>
  )
}

function Hosts() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/hosts",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Flex justify="space-between" align="flex-start" pt={12} mb={4}>
        <Box>
          <Heading size="md">Hosts</Heading>
          <Text color="fg.muted" fontSize="sm" mt={1}>
            Network devices that authenticate against the TACACS+ server.
          </Text>
        </Box>
      </Flex>
      <Flex mt={4} align="center" justify="space-between">
        <AddHost />
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by name, IP address, description..."
        />
      </Flex>
      <HostsTable />
    </Container>
  )
}
