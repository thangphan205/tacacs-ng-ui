import {
  Badge,
  Box,
  Button,
  Container,
  EmptyState,
  Flex,
  Heading,
  IconButton,
  Link,
  Table,
  Text,
  VStack,
  HStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Fragment, useState } from "react"
import {
  FiChevronDown,
  FiChevronRight,
  FiEdit,
  FiExternalLink,
  FiPlus,
  FiSearch,
  FiSliders,
  FiTrash2,
} from "react-icons/fi"
import { z } from "zod"

import {
  RulesetscriptsetsService,
  RulesetscriptsService,
  RulesetsService,
} from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { RulesetActionsMenu } from "@/components/Common/RulesetActionsMenu"
import { SearchBox } from "@/components/Common/SearchBox"
import PendingRulesets from "@/components/Pending/PendingRulesets"
import AddRulesetScriptSet from "@/components/RulesetScriptSets/AddRulesetScriptSet"
import DeleteRulesetScriptSet from "@/components/RulesetScriptSets/DeleteRulesetScriptSet"
import EditRulesetScriptSet from "@/components/RulesetScriptSets/EditRulesetScriptSet"
import AddRulesetScript from "@/components/RulesetScripts/AddRulesetScript"
import DeleteRulesetScript from "@/components/RulesetScripts/DeleteRulesetScript"
import EditRulesetScript from "@/components/RulesetScripts/EditRulesetScript"
import AddRuleset from "@/components/Rulesets/AddRuleset"
import PreviewRuleset from "@/components/Rulesets/PreviewRuleset"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"
import { Tooltip } from "@/components/ui/tooltip"

const rulesetsSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 10

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
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({})

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getRulesetsQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  // Fetch all scripts for nested visualization
  const { data: scriptsData } = useQuery({
    queryFn: () => RulesetscriptsService.readRulesetscripts({ limit: 1000 }),
    queryKey: ["rulesetscripts", "all"],
  })

  // Fetch all script sets for nested visualization
  const { data: scriptSetsData } = useQuery({
    queryFn: () =>
      RulesetscriptsetsService.readRulesetscriptsets({ limit: 1000 }),
    queryKey: ["rulesetscriptsets", "all"],
  })

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => ({
      ...prev,
      [id]: !prev[id],
    }))
  }

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
          <Box borderWidth="1px" borderRadius="xl" overflow="hidden" bg="bg.panel" mt={6} shadow="sm">
            <Table.Root
              size={{ base: "sm", md: "md" }}
              tableLayout="fixed"
              w="full"
            >
              <Table.Header bg="bg.muted">
                <Table.Row>
            <Table.ColumnHeader w="6%" />
            <Table.ColumnHeader w="25%">Name</Table.ColumnHeader>
            <Table.ColumnHeader w="15%">Generate</Table.ColumnHeader>
            <Table.ColumnHeader w="15%">Fallback Action</Table.ColumnHeader>
            <Table.ColumnHeader w="31%">Description</Table.ColumnHeader>
            <Table.ColumnHeader w="8%">Actions</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {rulesets?.map((ruleset) => {
            const isExpanded = !!expandedRows[ruleset.id]
            const rulesetScripts =
              scriptsData?.data.filter(
                (s) => s.ruleset_id === ruleset.id,
              ) || []

            return (
              <Fragment key={ruleset.id}>
                <Table.Row opacity={isPlaceholderData ? 0.5 : 1}>
                  <Table.Cell>
                    <Tooltip content={isExpanded ? "Click to collapse" : "Click to expand and view scripts"} showArrow placement="right">
                      <IconButton
                        variant="ghost"
                        size="xs"
                        onClick={() => toggleRow(ruleset.id)}
                        aria-label="Expand ruleset scripts"
                      >
                        {isExpanded ? <FiChevronDown /> : <FiChevronRight />}
                      </IconButton>
                    </Tooltip>
                  </Table.Cell>
                  <Table.Cell fontWeight="medium" truncate>
                    {ruleset.name}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={ruleset.generate_config ? "green" : "red"} variant="subtle" size="sm">
                      {ruleset.generate_config ? "Yes" : "No"}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      variant="subtle"
                      colorPalette={
                        ruleset.action === "permit" ? "green" : "orange"
                      }
                    >
                      {ruleset.action}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell
                    color={!ruleset.description ? "gray" : "inherit"}
                    truncate
                  >
                    {ruleset.description || "N/A"}
                  </Table.Cell>
                  <Table.Cell>
                    <RulesetActionsMenu ruleset={ruleset} />
                  </Table.Cell>
                </Table.Row>
                {isExpanded && (
                  <Table.Row>
                    <Table.Cell
                      colSpan={6}
                      p={4}
                      bg="bg.subtle"
                      borderBottomWidth="1px"
                      borderColor="border.subtle"
                        >
                          <Flex justify="space-between" align="center" mb={3}>
                            <Heading
                              size="xs"
                              textTransform="uppercase"
                              letterSpacing="wider"
                              color="teal.600"
                            >
                              Ruleset Script Structure ({rulesetScripts.length})
                            </Heading>
                            <AddRulesetScript
                              rulesetId={ruleset.id}
                              buttonElement={
                                <Button
                                  size="xs"
                                  variant="outline"
                                  colorPalette="teal"
                                >
                                  <FiPlus /> Add Script Block
                                </Button>
                              }
                            />
                          </Flex>
                          {rulesetScripts.length === 0 ? (
                            <Text fontSize="sm" color="fg.muted" py={2}>
                              No scripts configured. Click "Add Script Block" to
                              get started.
                            </Text>
                          ) : (
                            <VStack align="stretch" gap={3} w="full">
                              {rulesetScripts.map((script) => {
                                const scriptSets =
                                  scriptSetsData?.data.filter(
                                    (ss) => ss.rulesetscript_id === script.id,
                                  ) || []
                                return (
                                  <Box
                                    key={script.id}
                                    p={3}
                                    bg="bg.panel"
                                    borderWidth="1px"
                                    borderRadius="md"
                                    borderColor="border.subtle"
                                    position="relative"
                                  >
                                    <Flex
                                      justify="space-between"
                                      align="start"
                                      mb={2}
                                    >
                                      <Flex align="center" gap={2} wrap="wrap">
                                        <Badge
                                          colorPalette="teal"
                                          variant="solid"
                                          fontSize="xs"
                                        >
                                          {script.condition}
                                        </Badge>
                                        <Text
                                          fontSize="sm"
                                          fontWeight="semibold"
                                          fontFamily="mono"
                                        >
                                          ({script.key} == "{script.value}")
                                        </Text>
                                        {script.description && (
                                          <Text fontSize="xs" color="fg.muted">
                                            — {script.description}
                                          </Text>
                                        )}
                                      </Flex>
                                      <Flex align="center" gap={1}>
                                        <EditRulesetScript
                                          rulesetscript={script}
                                          buttonElement={
                                            <IconButton
                                              size="xs"
                                              variant="ghost"
                                              aria-label="Edit script"
                                            >
                                              <FiEdit />
                                            </IconButton>
                                          }
                                        />
                                        <DeleteRulesetScript
                                          rulesetscript={script}
                                          buttonElement={
                                            <IconButton
                                              size="xs"
                                              variant="ghost"
                                              colorPalette="red"
                                              aria-label="Delete script"
                                            >
                                              <FiTrash2 />
                                            </IconButton>
                                          }
                                        />
                                      </Flex>
                                    </Flex>

                                    <Box
                                      pl={4}
                                      ml={2}
                                      borderLeftWidth="2px"
                                      borderColor="border.muted"
                                      mb={2}
                                    >
                                      {scriptSets.length === 0 ? (
                                        <Text
                                          fontSize="xs"
                                          color="fg.muted"
                                          fontStyle="italic"
                                          mb={2}
                                        >
                                          No key-value assignments configured.
                                        </Text>
                                      ) : (
                                        <VStack
                                          align="stretch"
                                          gap={1.5}
                                          mb={2}
                                        >
                                          {scriptSets.map((set) => (
                                            <Flex
                                              key={set.id}
                                              align="center"
                                              justify="space-between"
                                              bg="bg.subtle"
                                              py={1}
                                              px={2}
                                              borderRadius="sm"
                                              borderWidth="1px"
                                              borderColor="border.subtle"
                                            >
                                              <Flex align="center" gap={2}>
                                                <Badge
                                                  colorPalette="purple"
                                                  variant="outline"
                                                  size="sm"
                                                >
                                                  set
                                                </Badge>
                                                <Text
                                                  fontSize="xs"
                                                  fontFamily="mono"
                                                  fontWeight="medium"
                                                >
                                                  {set.key} = "{set.value}"
                                                </Text>
                                                {set.description && (
                                                  <Text
                                                    fontSize="2xs"
                                                    color="fg.muted"
                                                  >
                                                    ({set.description})
                                                  </Text>
                                                )}
                                              </Flex>
                                              <Flex align="center" gap={0.5}>
                                                <EditRulesetScriptSet
                                                  rulesetscriptset={set}
                                                  buttonElement={
                                                    <IconButton
                                                      size="2xs"
                                                      variant="ghost"
                                                      aria-label="Edit set"
                                                    >
                                                      <FiEdit fontSize="10px" />
                                                    </IconButton>
                                                  }
                                                />
                                                <DeleteRulesetScriptSet
                                                  rulesetscriptset={set}
                                                  buttonElement={
                                                    <IconButton
                                                      size="2xs"
                                                      variant="ghost"
                                                      colorPalette="red"
                                                      aria-label="Delete set"
                                                    >
                                                      <FiTrash2 fontSize="10px" />
                                                    </IconButton>
                                                  }
                                                />
                                              </Flex>
                                            </Flex>
                                          ))}
                                        </VStack>
                                      )}
                                      <AddRulesetScriptSet
                                        rulesetscriptId={script.id}
                                        buttonElement={
                                          <Button
                                            size="xs"
                                            variant="ghost"
                                            colorPalette="teal"
                                            height="6"
                                            p="1"
                                          >
                                            <FiPlus fontSize="12px" /> Add
                                            Variable Assignment
                                          </Button>
                                        }
                                      />
                                    </Box>

                                    <Flex align="center" gap={1.5} pl={2}>
                                      <Text
                                        fontSize="xs"
                                        fontWeight="bold"
                                        color="fg.muted"
                                      >
                                        Result action:
                                      </Text>
                                      <Badge
                                        colorPalette={
                                          script.action === "permit"
                                            ? "green"
                                            : "orange"
                                        }
                                        variant="subtle"
                                      >
                                        {script.action}
                                      </Badge>
                                    </Flex>
                                  </Box>
                                )
                              })}
                            </VStack>
                          )}
                          <Box
                            mt={4}
                            pt={3}
                            borderTopWidth="1px"
                            borderColor="border.subtle"
                          >
                            <Flex align="center" gap={2}>
                              <Text
                                fontSize="xs"
                                fontWeight="bold"
                                color="fg.muted"
                              >
                                Fallback Action:
                              </Text>
                              <Badge
                                colorPalette={
                                  ruleset.action === "permit"
                                    ? "green"
                                    : "orange"
                                }
                                variant="solid"
                              >
                                {ruleset.action}
                              </Badge>
                              <Text
                                fontSize="xs"
                                color="fg.muted"
                                display="inline-flex"
                                alignItems="center"
                                gap={1}
                              >
                                (Applied if none of the script blocks above
                                match the request. Learn more in the{" "}
                                <Link
                                  href="https://projects.pro-bono-publico.de/event-driven-servers/doc/tac_plus-ng.html#_scripts"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  color="blue.500"
                                  display="inline-flex"
                                  alignItems="center"
                                  gap={0.5}
                                >
                                  official documentation{" "}
                                  <FiExternalLink size="12px" />
                                </Link>
                                )
                              </Text>
                            </Flex>
                          </Box>
                        </Table.Cell>
                      </Table.Row>
                    )}
                  </Fragment>
                )
              })}
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
      <PageHeader
        title="Rulesets Management"
        description="Rulesets match client properties (like usernames, client IPs, or service options) and map them to appropriate Profiles. Click the chevron (>) on any row to expand and view its script structure."
        icon={FiSliders}
      />
      <Flex mt={6} align="center" justify="space-between" gap={4} wrap="wrap">
        <HStack gap={3}>
          <AddRuleset />
          <PreviewRuleset />
        </HStack>
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
export default Rulesets
