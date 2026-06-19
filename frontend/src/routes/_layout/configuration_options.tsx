import {
  Box,
  Code,
  Container,
  EmptyState,
  Flex,
  HStack,
  IconButton,
  Link,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import { FiCheck, FiCopy, FiExternalLink, FiSearch, FiSliders } from "react-icons/fi"
import { z } from "zod"

import { ConfigurationOptionsService } from "@/client"
import { ConfigurationOptionActionsMenu } from "@/components/Common/ConfigurationOptionActionsMenu"
import { PageHeader } from "@/components/Common/PageHeader"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { SearchBox } from "@/components/Common/SearchBox"
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
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 5

function getConfigurationOptionsQueryOptions({
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
      ConfigurationOptionsService.readConfigurationOptions({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["configuration_options", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/configuration_options")({
  component: ConfigurationOptions,
  validateSearch: (search) => configuration_optionsSearchSchema.parse(search),
})

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <IconButton
      variant="ghost"
      size="xs"
      onClick={handleCopy}
      aria-label="Copy ID"
      color="fg.muted"
      _hover={{ color: "teal.fg" }}
    >
      {copied ? <FiCheck color="green" /> : <FiCopy />}
    </IconButton>
  )
}

function ConfigurationOptionsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getConfigurationOptionsQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/configuration_options",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const configuration_options = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      {isLoading ? (
        <PendingConfigurationOptions />
      ) : configuration_options.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>
                You don't have any configuration options yet
              </EmptyState.Title>
              <EmptyState.Description>
                Add a new configuration option to get started
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Box borderWidth="1px" borderRadius="xl" overflow="hidden" bg="bg.panel" mt={6} shadow="sm">
            <Table.Root size={{ base: "sm", md: "md" }}>
              <Table.Header bg="bg.muted">
                <Table.Row>
                  <Table.ColumnHeader w="xs">ID</Table.ColumnHeader>
                  <Table.ColumnHeader w="sm">Name</Table.ColumnHeader>
                  <Table.ColumnHeader w="md">Config Option</Table.ColumnHeader>
                  <Table.ColumnHeader w="md">Description</Table.ColumnHeader>
                  <Table.ColumnHeader w="24" textAlign="right">Actions</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {configuration_options?.map((configuration_option) => (
                  <Table.Row
                    key={configuration_option.id}
                    opacity={isPlaceholderData ? 0.5 : 1}
                    _hover={{ bg: "bg.muted/50" }}
                    transition="background 0.2s"
                  >
                    <Table.Cell>
                      <HStack gap={2}>
                        <Text fontFamily="mono" fontSize="xs" color="fg.muted">
                          {configuration_option.id.substring(0, 8)}...
                        </Text>
                        <CopyButton text={configuration_option.id} />
                      </HStack>
                    </Table.Cell>
                    <Table.Cell truncate maxW="sm" fontWeight="medium">
                      {configuration_option.name}
                    </Table.Cell>
                    <Table.Cell>
                      <Code fontFamily="mono" fontSize="xs">
                        {configuration_option.config_option}
                      </Code>
                    </Table.Cell>
                    <Table.Cell
                      color={
                        !configuration_option.description ? "gray" : "inherit"
                      }
                      truncate
                      maxW="sm"
                    >
                      {configuration_option.description || "—"}
                    </Table.Cell>
                    <Table.Cell textAlign="right">
                      <ConfigurationOptionActionsMenu
                        configuration_option={configuration_option}
                      />
                    </Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
          </Box>
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

function ConfigurationOptions() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/configuration_options",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <PageHeader
        title="Configuration Options"
        description="Define raw settings blocks using native tac_plus-ng syntax for advanced features not directly mapped to UI forms."
        icon={FiSliders}
      />
      <Box mt={3} fontSize="xs" color="fg.muted">
        For advanced use cases, refer to the{" "}
        <Link
          href="https://projects.pro-bono-publico.de/event-driven-servers/doc/tac_plus-ng.html"
          color="blue.500"
          target="_blank"
          rel="noopener noreferrer"
        >
          official documentation <FiExternalLink style={{ display: "inline", verticalAlign: "middle" }} />
        </Link>
      </Box>
      <Flex mt={6} align="center" justify="space-between" gap={4} wrap="wrap">
        <HStack gap={3}>
          <AddConfigurationOption />
          <PreviewTacacsConfig />
        </HStack>
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by name, config option, description..."
        />
      </Flex>
      <ConfigurationOptionsTable />
    </Container>
  )
}
