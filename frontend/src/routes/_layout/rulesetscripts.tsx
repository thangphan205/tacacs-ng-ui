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

import { RulesetscriptsService } from "@/client"
import { RulesetScriptActionsMenu } from "@/components/Common/RulesetScriptActionsMenu"
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

const PER_PAGE = 5

function getRulesetScriptsQueryOptions({
  page,
  search,
}: {
  page: number
  search?: string
}) {
  return {
    queryFn: () =>
      RulesetscriptsService.readRulesetscripts({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["rulesetscripts", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/rulesetscripts")({
  component: RulesetScripts,
  validateSearch: (search) => rulesetscriptsSearchSchema.parse(search),
})

function RulesetScriptsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [localSearch, setLocalSearch] = useState(search ?? "")
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getRulesetScriptsQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  useEffect(() => {
    setLocalSearch(search ?? "")
  }, [search])

  const setPage = (page: number) => {
    navigate({
      to: "/rulesetscripts",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      navigate({
        to: "/rulesetscripts",
        search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
      })
    }, 500)
  }

  const rulesetscripts = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      <Flex mt={4} justifyContent="flex-end">
        <InputGroup maxW="sm">
          <Input
            type="text"
            placeholder="Search by condition, key, value, description..."
            value={localSearch}
            onChange={handleSearchChange}
            size="sm"
          />
        </InputGroup>
      </Flex>
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
          <Table.Root size={{ base: "sm", md: "md" }} mt={2}>
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader w="sm">ID</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Ruleset Parent</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Condition</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Key</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Value</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Action</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {rulesetscripts?.map((rulesetscript) => (
                <Table.Row
                  key={rulesetscript.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell truncate maxW="sm">
                    {rulesetscript.id}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {rulesetscript.ruleset_name}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {rulesetscript.condition}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {rulesetscript.key}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {rulesetscript.value}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {rulesetscript.action}
                  </Table.Cell>
                  <Table.Cell
                    color={!rulesetscript.description ? "gray" : "inherit"}
                    truncate
                    maxW="30%"
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

function RulesetScripts() {
  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        RulesetScripts Management
      </Heading>
      <Flex gap={2}>
        <AddRulesetScript />
        <PreviewRuleset />
      </Flex>
      <RulesetScriptsTable />
    </Container>
  )
}
