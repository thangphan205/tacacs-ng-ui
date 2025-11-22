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

import { RulesetscriptsetsService } from "@/client"
import { RulesetScriptSetActionsMenu } from "@/components/Common/RulesetScriptSetActionsMenu"
import AddRulesetScriptSet from "@/components/RulesetScriptSets/AddRulesetScriptSet"
import PreviewRuleset from "@/components/Rulesets/PreviewRuleset"
import PendingRulesetScriptSets from "@/components/Pending/PendingRulesetScriptSets"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const rulesetscriptsetsSearchSchema = z.object({
  page: z.number().catch(1),
})

const PER_PAGE = 5

function getRulesetScriptSetsQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      RulesetscriptsetsService.readRulesetscriptsets({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["rulesetscriptsets", { page }],
  }
}

export const Route = createFileRoute("/_layout/rulesetscriptsets")({
  component: RulesetScriptSets,
  validateSearch: (search) => rulesetscriptsetsSearchSchema.parse(search),
})

function RulesetScriptSetsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getRulesetScriptSetsQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/rulesetscriptsets",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const rulesetscriptsets = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  if (isLoading) {
    return <PendingRulesetScriptSets />
  }

  if (rulesetscriptsets.length === 0) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSearch />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>You don't have any rulesetscriptsets yet</EmptyState.Title>
            <EmptyState.Description>
              Add a new rulesetscriptset to get started
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
            <Table.ColumnHeader w="sm">Ruleset</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Ruleset Script Block</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Set Key</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Set Value</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Description</Table.ColumnHeader>
            <Table.ColumnHeader w="sm">Actions</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {rulesetscriptsets?.map((rulesetscriptset) => (
            <Table.Row key={rulesetscriptset.id} opacity={isPlaceholderData ? 0.5 : 1}>
              <Table.Cell truncate maxW="sm">
                {rulesetscriptset.id}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {rulesetscriptset.ruleset_name}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {rulesetscriptset.rulesetscript_block}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {rulesetscriptset.key}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {rulesetscriptset.value}
              </Table.Cell>
              <Table.Cell
                color={!rulesetscriptset.description ? "gray" : "inherit"}
                truncate
                maxW="30%"
              >
                {rulesetscriptset.description || "N/A"}
              </Table.Cell>
              <Table.Cell>
                <RulesetScriptSetActionsMenu rulesetscriptset={rulesetscriptset} />
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

function RulesetScriptSets() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
        RulesetScriptSets Management
      </Heading>
      <Flex gap={2}>
        <AddRulesetScriptSet />
        <PreviewRuleset />
      </Flex>
      <RulesetScriptSetsTable />
    </Container>
  )
}
