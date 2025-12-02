import {
  Code,
  Container,
  EmptyState,
  Flex,
  Heading,
  Table,
  VStack,
  Link
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiSearch } from "react-icons/fi"
import { z } from "zod"

import { ConfigurationOptionsService } from "@/client"
import { ConfigurationOptionActionsMenu } from "@/components/Common/ConfigurationOptionActionsMenu"
import AddConfigurationOption from "@/components/ConfigurationOptions/AddConfigurationOption"
import PendingConfigurationOptions from "@/components/Pending/PendingConfigurationOptions"
import PreviewTacacsConfig from "@/components/TacacsConfigs/PreviewTacacsConfig"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const configuration_optionsSearchSchema = z.object({
  page: z.number().catch(1),
})

const PER_PAGE = 5

function getConfigurationOptionsQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      ConfigurationOptionsService.readConfigurationOptions({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["configuration_options", { page }],
  }
}

export const Route = createFileRoute("/_layout/configuration_options")({
  component: ConfigurationOptions,
  validateSearch: (search) => configuration_optionsSearchSchema.parse(search),
})

function ConfigurationOptionsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getConfigurationOptionsQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/configuration_options",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const configuration_options = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  if (isLoading) {
    return <PendingConfigurationOptions />
  }

  if (configuration_options.length === 0) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSearch />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>You don't have any configuration_options yet</EmptyState.Title>
            <EmptyState.Description>
              Add a new configuration_option to get started
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
            <Table.ColumnHeader w="sm">Config Option</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {configuration_options?.map((configuration_option) => (
            <Table.Row key={configuration_option.id} opacity={isPlaceholderData ? 0.5 : 1}>
              <Table.Cell truncate maxW="sm">
                {configuration_option.id}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {configuration_option.name}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {configuration_option.config_option}
              </Table.Cell>
              <Table.Cell
                color={!configuration_option.description ? "gray" : "inherit"}
                truncate
                maxW="30%"
              >
                {configuration_option.description || "N/A"}
              </Table.Cell>
              <Table.Cell>
                <ConfigurationOptionActionsMenu configuration_option={configuration_option} />
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

function ConfigurationOptions() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
        Configuration Options Management
      </Heading>
      For advanced use cases not covered by the UI, you can directly use{" "}
      <Code>tac_plus-ng</Code> script syntax. For details, see the{" "}
      <Link href="https://projects.pro-bono-publico.de/event-driven-servers/doc/tac_plus-ng.html" color="blue.500">
        official documentation
      </Link>

      <Flex gap={2}>
        <AddConfigurationOption />
        <PreviewTacacsConfig />
      </Flex>
      <ConfigurationOptionsTable />
    </Container>
  )
}
