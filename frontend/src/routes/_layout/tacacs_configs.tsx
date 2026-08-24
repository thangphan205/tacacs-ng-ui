import {
  Alert,
  Badge,
  Box,
  Button,
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
import { FiFileText, FiSearch } from "react-icons/fi"
import { z } from "zod"

import { TacacsConfigsService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { SearchBox } from "@/components/Common/SearchBox"
import { TacacsConfigActionsMenu } from "@/components/Common/TacacsConfigActionsMenu"
import PendingTacacsConfigs from "@/components/Pending/PendingTacacsConfigs"
import AddTacacsConfig from "@/components/TacacsConfigs/AddTacacsConfig"
import CompareConfigs from "@/components/TacacsConfigs/CompareConfigs"
import PreviewTacacsConfig from "@/components/TacacsConfigs/PreviewTacacsConfig"
import ShowActiveTacacsConfig from "@/components/TacacsConfigs/ShowActiveTacacsConfig"
import ShowTacacsConfig from "@/components/TacacsConfigs/ShowTacacsConfig"
import { SyncToStandby } from "@/components/TacacsConfigs/SyncToStandby"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const tacacs_configsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 5

function getTacacsConfigsQueryOptions({
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
      TacacsConfigsService.readTacacsConfigs({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["tacacs_configs", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/tacacs_configs")({
  component: TacacsConfigs,
  validateSearch: (search) => tacacs_configsSearchSchema.parse(search),
})

/**
 * Compares the config the database would generate against the one the daemon is
 * actually running, so edits made outside this page — the entity pages, or an
 * MCP client holding a write key — do not sit unnoticed. Neither of those can
 * deploy; only Generate + Activate here does.
 */
function PendingChangesAlert() {
  const { data: preview, isLoading: previewLoading } = useQuery({
    queryKey: ["tacacs_configs", "preview"],
    queryFn: () => TacacsConfigsService.generatePreviewTacacsConfig(),
  })

  // Errors when no config has ever been activated, which is a valid state.
  const {
    data: active,
    isLoading: activeLoading,
    isError: activeMissing,
  } = useQuery({
    queryKey: ["tacacs_configs", "active"],
    queryFn: () => TacacsConfigsService.getActiveTacacsConfig(),
    retry: false,
  })

  if (previewLoading || activeLoading) return null

  const generated = preview?.data ?? ""
  const running = activeMissing ? null : (active?.data ?? "")
  const inSync = running !== null && generated.trim() === running.trim()

  if (inSync) {
    return (
      <Alert.Root status="success" mb={4} borderRadius="md">
        <Alert.Indicator />
        <Alert.Content>
          <Alert.Title>Running config matches the database</Alert.Title>
          <Alert.Description>
            Nothing to apply. Any later change — from these pages or from an MCP
            client — needs a new configuration generated and activated here.
          </Alert.Description>
        </Alert.Content>
      </Alert.Root>
    )
  }

  return (
    <Alert.Root status="warning" mb={4} borderRadius="md">
      <Alert.Indicator />
      <Alert.Content>
        <Alert.Title>
          {running === null
            ? "No configuration is active yet"
            : "Unapplied changes in the database"}
        </Alert.Title>
        <Alert.Description>
          {running === null
            ? "Generate a configuration and activate it to start serving it."
            : "The database no longer matches the config tac_plus-ng is running. Changes made on the entity pages, or by an MCP client, only take effect once you generate a new configuration and activate it here."}
        </Alert.Description>
      </Alert.Content>
    </Alert.Root>
  )
}

function TacacsConfigsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getTacacsConfigsQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/tacacs_configs",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const tacacs_configs = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      {isLoading ? (
        <PendingTacacsConfigs />
      ) : tacacs_configs.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>No configurations yet</EmptyState.Title>
              <EmptyState.Description>
                Generate a new configuration to get started
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size={{ base: "sm", md: "md" }} mt={2}>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Filename</Table.ColumnHeader>
                <Table.ColumnHeader w="28">Status</Table.ColumnHeader>
                <Table.ColumnHeader>Description</Table.ColumnHeader>
                <Table.ColumnHeader w="40">Created At</Table.ColumnHeader>
                <Table.ColumnHeader w="16">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {tacacs_configs.map((tacacs_config) => (
                <Table.Row
                  key={tacacs_config.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                  bg={tacacs_config.active ? "green.subtle" : undefined}
                >
                  <Table.Cell>
                    <ShowTacacsConfig tacacs_config={tacacs_config}>
                      <Button
                        variant="ghost"
                        size="sm"
                        colorPalette={tacacs_config.active ? "green" : "gray"}
                        fontWeight={
                          tacacs_config.active ? "semibold" : "normal"
                        }
                      >
                        <FiFileText />
                        {tacacs_config.filename}
                      </Button>
                    </ShowTacacsConfig>
                  </Table.Cell>
                  <Table.Cell>
                    {tacacs_config.active ? (
                      <Badge colorPalette="green" variant="solid" size="sm">
                        Active
                      </Badge>
                    ) : (
                      <Badge colorPalette="gray" variant="outline" size="sm">
                        Inactive
                      </Badge>
                    )}
                  </Table.Cell>
                  <Table.Cell
                    color={!tacacs_config.description ? "fg.muted" : "inherit"}
                    truncate
                    maxW="xs"
                  >
                    {tacacs_config.description || "—"}
                  </Table.Cell>
                  <Table.Cell fontSize="sm" color="fg.muted">
                    {new Date(tacacs_config.created_at).toLocaleString(
                      "en-US",
                      { hour12: false },
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    <TacacsConfigActionsMenu tacacs_config={tacacs_config} />
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

function TacacsConfigs() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/tacacs_configs",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Flex justify="space-between" align="flex-start" pt={12} mb={4}>
        <Box>
          <Heading size="md">TACACS+ Configuration</Heading>
          <Text color="fg.muted" fontSize="sm" mt={1}>
            Generate → Preview → Activate. Each snapshot is versioned.
          </Text>
        </Box>
      </Flex>

      <PendingChangesAlert />

      <Flex mt={4} align="center" justify="space-between">
        <Flex gap={2} flexWrap="wrap">
          <AddTacacsConfig />
          <PreviewTacacsConfig />
          <ShowActiveTacacsConfig />
          <CompareConfigs />
          <SyncToStandby />
        </Flex>
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by filename, description..."
        />
      </Flex>

      <TacacsConfigsTable />
    </Container>
  )
}
