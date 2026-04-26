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

import { RulesetsService } from "@/client"
import { RulesetActionsMenu } from "@/components/Common/RulesetActionsMenu"
import PendingRulesets from "@/components/Pending/PendingRulesets"
import AddRuleset from "@/components/Rulesets/AddRuleset"
import PreviewRuleset from "@/components/Rulesets/PreviewRuleset"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const rulesetsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const PER_PAGE = 5

function getRulesetsQueryOptions({
  page,
  search,
}: {
  page: number
  search?: string
}) {
  return {
    queryFn: () =>
      RulesetsService.readRulesets({
        skip: (page - 1) * PER_PAGE,
        limit: PER_PAGE,
        search,
      }),
    queryKey: ["rulesets", { page, search }],
  }
}

export const Route = createFileRoute("/_layout/rulesets")({
  component: Rulesets,
  validateSearch: (search) => rulesetsSearchSchema.parse(search),
})

function RulesetsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [localSearch, setLocalSearch] = useState(search ?? "")
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getRulesetsQueryOptions({ page, search }),
    placeholderData: (prevData) => prevData,
  })

  useEffect(() => {
    setLocalSearch(search ?? "")
  }, [search])

  const setPage = (page: number) => {
    navigate({
      to: "/rulesets",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      navigate({
        to: "/rulesets",
        search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
      })
    }, 500)
  }

  const rulesets = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      <Flex mt={4} justifyContent="flex-end">
        <InputGroup maxW="sm">
          <Input
            type="text"
            placeholder="Search by name, action, description..."
            value={localSearch}
            onChange={handleSearchChange}
            size="sm"
          />
        </InputGroup>
      </Flex>
      {isLoading ? (
        <PendingRulesets />
      ) : rulesets.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>You don't have any rulesets yet</EmptyState.Title>
              <EmptyState.Description>
                Add a new ruleset to get started
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
                <Table.ColumnHeader w="sm">Name</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Action</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
                <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {rulesets?.map((ruleset) => (
                <Table.Row
                  key={ruleset.id}
                  opacity={isPlaceholderData ? 0.5 : 1}
                >
                  <Table.Cell truncate maxW="sm">
                    {ruleset.id}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {ruleset.name}
                  </Table.Cell>
                  <Table.Cell truncate maxW="sm">
                    {ruleset.action}
                  </Table.Cell>
                  <Table.Cell
                    color={!ruleset.description ? "gray" : "inherit"}
                    truncate
                    maxW="30%"
                  >
                    {ruleset.description || "N/A"}
                  </Table.Cell>
                  <Table.Cell>
                    <RulesetActionsMenu ruleset={ruleset} />
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

function Rulesets() {
  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        Rulesets Management
      </Heading>
      <Flex gap={2}>
        <AddRuleset />
        <PreviewRuleset />
      </Flex>
      <RulesetsTable />
    </Container>
  )
}
