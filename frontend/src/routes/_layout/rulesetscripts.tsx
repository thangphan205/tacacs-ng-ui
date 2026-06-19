import {
  Badge,
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
import { FiSearch } from "react-icons/fi"
import { z } from "zod"

import { RulesetscriptsService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { RulesetScriptActionsMenu } from "@/components/Common/RulesetScriptActionsMenu"
import { SearchBox } from "@/components/Common/SearchBox"
import PendingRulesetScripts from "@/components/Pending/PendingRulesetScripts"
import AddRulesetScript from "@/components/RulesetScripts/AddRulesetScript"
import PreviewRuleset from "@/components/Rulesets/PreviewRuleset"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const rulesetscriptsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 5

function getRulesetScriptsQueryOptions({
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
      RulesetscriptsService.readRulesetscripts({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["rulesetscripts", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/rulesetscripts")({
  component: RulesetScripts,
  validateSearch: (search) => rulesetscriptsSearchSchema.parse(search),
})

function RulesetScriptsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getRulesetScriptsQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/rulesetscripts",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const rulesetscripts = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      {isLoading ? (
        <PendingRulesetScripts />
      ) : rulesetscripts.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>
                You don't have any rulesetscripts yet
              </EmptyState.Title>
              <EmptyState.Description>
                Add a new rulesetscript to get started
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
                <Table.ColumnHeader w="28%">
                  Ruleset / Condition
                </Table.ColumnHeader>
                <Table.ColumnHeader w="12%">Key</Table.ColumnHeader>
                <Table.ColumnHeader w="15%">Value</Table.ColumnHeader>
                <Table.ColumnHeader w="10%">Action</Table.ColumnHeader>
                <Table.ColumnHeader w="27%">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="8%">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {rulesetscripts?.map((rulesetscript) => (
                <Table.Row
                  key={rulesetscript.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell>
                    <Text fontWeight="medium" truncate>
                      {rulesetscript.ruleset_name}
                    </Text>
                    <Badge
                      variant="subtle"
                      colorPalette="teal"
                      mt={0.5}
                      fontSize="xs"
                    >
                      {rulesetscript.condition}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell truncate>{rulesetscript.key}</Table.Cell>
                  <Table.Cell truncate>{rulesetscript.value}</Table.Cell>
                  <Table.Cell truncate>{rulesetscript.action}</Table.Cell>
                  <Table.Cell
                    color={!rulesetscript.description ? "gray" : "inherit"}
                    truncate
                  >
                    {rulesetscript.description || "N/A"}
                  </Table.Cell>
                  <Table.Cell>
                    <RulesetScriptActionsMenu rulesetscript={rulesetscript} />
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

function RulesetScripts() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/rulesetscripts",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        RulesetScripts Management
      </Heading>
      <Flex mt={4} align="center" justify="space-between">
        <Flex gap={2}>
          <AddRulesetScript />
          <PreviewRuleset />
        </Flex>
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by condition, key, value, description..."
        />
      </Flex>
      <RulesetScriptsTable />
    </Container>
  )
}
