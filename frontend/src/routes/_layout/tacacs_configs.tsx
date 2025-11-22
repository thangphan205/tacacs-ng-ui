import {
  Container,
  Badge,
  Button,
  EmptyState,
  Flex,
  Heading,
  Table,
  VStack,
  Code
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiSearch, FiEye } from "react-icons/fi"
import { z } from "zod"

import { TacacsConfigsService } from "@/client"
import { TacacsConfigActionsMenu } from "@/components/Common/TacacsConfigActionsMenu"
import AddTacacsConfig from "@/components/TacacsConfigs/AddTacacsConfig"
import ShowTacacsConfig from "@/components/TacacsConfigs/ShowTacacsConfig"
import PreviewTacacsConfig from "@/components/TacacsConfigs/PreviewTacacsConfig"
import ShowActiveTacacsConfig from "@/components/TacacsConfigs/ShowActiveTacacsConfig"
import PendingTacacsConfigs from "@/components/Pending/PendingTacacsConfigs"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const tacacs_configsSearchSchema = z.object({
  page: z.number().catch(1),
})

const PER_PAGE = 5

function getTacacsConfigsQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      TacacsConfigsService.readTacacsConfigs({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["tacacs_configs", { page }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_configs")({
  component: TacacsConfigs,
  validateSearch: (search) => tacacs_configsSearchSchema.parse(search),
})

function TacacsConfigsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsConfigsQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_configs",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const tacacs_configs = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  if (isLoading) {
    return <PendingTacacsConfigs />
  }

  if (tacacs_configs.length === 0) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSearch />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>You don't have any tacacs_configs yet</EmptyState.Title>
            <EmptyState.Description>
              Add a new tacacs_config to get started
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
            <Table.ColumnHeader w="sm">Filename</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Active</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Created At</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {tacacs_configs?.map((tacacs_config) => (
            <Table.Row key={tacacs_config.id} opacity={isPlaceholderData ? 0.5 : 1}>
              <Table.Cell truncate maxW="sm">
                {tacacs_config.id}
              </Table.Cell>
              <Table.Cell truncate maxW="sm" cursor="pointer">
                <ShowTacacsConfig tacacs_config={tacacs_config}>
                  {tacacs_config.active ? (
                    <Button colorPalette="green"><FiEye />{tacacs_config.filename}</Button>
                  ) : (
                    <Button variant="ghost" colorPalette="gray"><FiEye />{tacacs_config.filename}</Button>
                  )}
                </ShowTacacsConfig>
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {tacacs_config.active ? (
                  <Badge variant="solid" colorPalette="green">Yes</Badge>
                ) : (
                  <Badge>No</Badge>
                )}
              </Table.Cell>
              <Table.Cell
                color={!tacacs_config.description ? "gray" : "inherit"}
                truncate
                maxW="30%"
              >
                {tacacs_config.description || "N/A"}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {new Date(tacacs_config.created_at).toLocaleDateString()}
              </Table.Cell>
              <Table.Cell>
                <TacacsConfigActionsMenu tacacs_config={tacacs_config} />
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

function TacacsConfigs() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
        TacacsConfigs Management
      </Heading>
      <Code size="md" colorPalette="red" variant="subtle" >
        Whenever you change the TACACS configuration, you must generate and activate the new configuration.
      </Code>
      <Flex gap={2}>
        <AddTacacsConfig />
        <PreviewTacacsConfig />
        <ShowActiveTacacsConfig />
      </Flex>
      <TacacsConfigsTable />
    </Container >
  )
}
