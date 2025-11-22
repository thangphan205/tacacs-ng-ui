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

import { RulesetsService } from "@/client"
import { RulesetActionsMenu } from "@/components/Common/RulesetActionsMenu"
import AddRuleset from "@/components/Rulesets/AddRuleset"
import PreviewRuleset from "@/components/Rulesets/PreviewRuleset"
import PendingRulesets from "@/components/Pending/PendingRulesets"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const rulesetsSearchSchema = z.object({
  page: z.number().catch(1),
})

const PER_PAGE = 5

function getRulesetsQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      RulesetsService.readRulesets({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["rulesets", { page }],
  }
}

export const Route = createFileRoute("/_layout/rulesets")({
  component: Rulesets,
  validateSearch: (search) => rulesetsSearchSchema.parse(search),
})

function RulesetsTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getRulesetsQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/rulesets",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const rulesets = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  if (isLoading) {
    return <PendingRulesets />
  }

  if (rulesets.length === 0) {
    return (
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
    )
  }

  return (
    <>
      <Table.Root size={{ base: "sm", md: "md" }}>
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
            <Table.Row key={ruleset.id} opacity={isPlaceholderData ? 0.5 : 1}>
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
  )
}

function Rulesets() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
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
