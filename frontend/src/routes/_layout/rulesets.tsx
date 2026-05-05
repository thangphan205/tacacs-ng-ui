import {
  Container,
  EmptyState,
  Flex,
  Heading,
  Table,
  VStack,
} from "@chakra-ui/react"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiSearch } from "react-icons/fi"
import { z } from "zod"

import { RulesetsService } from "@/client"
import { RulesetActionsMenu } from "@/components/Common/RulesetActionsMenu"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { SearchBox } from "@/components/Common/SearchBox"
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

const DEFAULT_PER_PAGE = 5

function getRulesetsQueryOptions({
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
      RulesetsService.readRulesets({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["rulesets", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/rulesets")({
  component: Rulesets,
  validateSearch: (search) => rulesetsSearchSchema.parse(search),
})

function RulesetsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getRulesetsQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/rulesets",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const rulesets = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      {isLoading ? (
        <PendingRulesets />
      ) : rulesets.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>
                You don't have any rulesets yet
              </EmptyState.Title>
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

function Rulesets() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/rulesets",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Heading size="md" pt={6}>
        Rulesets Management
      </Heading>
      <Flex mt={4} align="center" justify="space-between">
        <Flex gap={2}>
          <AddRuleset />
          <PreviewRuleset />
        </Flex>
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by name, action, description..."
        />
      </Flex>
      <RulesetsTable />
    </Container>
  )
}
