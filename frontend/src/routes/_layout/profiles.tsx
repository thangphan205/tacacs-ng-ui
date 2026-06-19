import {
  Badge,
  Box,
  Button,
  Container,
  EmptyState,
  Flex,
  Heading,
  HStack,
  IconButton,
  Link,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Fragment, useState } from "react"
import {
  FiChevronDown,
  FiChevronRight,
  FiEdit,
  FiExternalLink,
  FiFileText,
  FiPlus,
  FiSearch,
  FiTrash2,
} from "react-icons/fi"
import { z } from "zod"

import {
  ProfilescriptsetsService,
  ProfilescriptsService,
  ProfilesService,
} from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { ProfileActionsMenu } from "@/components/Common/ProfileActionsMenu"
import { SearchBox } from "@/components/Common/SearchBox"
import PendingProfiles from "@/components/Pending/PendingProfiles"
import AddProfileScriptSet from "@/components/ProfileScriptSets/AddProfileScriptSet"
import DeleteProfileScriptSet from "@/components/ProfileScriptSets/DeleteProfileScriptSet"
import EditProfileScriptSet from "@/components/ProfileScriptSets/EditProfileScriptSet"
import AddProfileScript from "@/components/ProfileScripts/AddProfileScript"
import DeleteProfileScript from "@/components/ProfileScripts/DeleteProfileScript"
import EditProfileScript from "@/components/ProfileScripts/EditProfileScript"
import AddProfile from "@/components/Profiles/AddProfile"
import PreviewProfile from "@/components/Profiles/PreviewProfile"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"
import { Tooltip } from "@/components/ui/tooltip"

const profilesSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 10

export const Route = createFileRoute("/_layout/profiles")({
  component: Profiles,
  validateSearch: (search) => profilesSearchSchema.parse(search),
})

// ── Profiles table list ───────────────────────────────────────────────────────

function ProfilesTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({})

  const { data, isLoading, isPlaceholderData } = useQuery({
    queryFn: () =>
      ProfilesService.readProfiles({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["profiles", { page, search, perPage }],
    placeholderData: (prev) => prev,
  })

  // Fetch all scripts for nested visualization
  const { data: scriptsData } = useQuery({
    queryFn: () => ProfilescriptsService.readProfilescripts({ limit: 1000 }),
    queryKey: ["profilescripts", "all"],
  })

  // Fetch all script sets for nested visualization
  const { data: scriptSetsData } = useQuery({
    queryFn: () =>
      ProfilescriptsetsService.readProfilescriptsets({ limit: 1000 }),
    queryKey: ["profilescriptsets", "all"],
  })

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => ({
      ...prev,
      [id]: !prev[id],
    }))
  }

  const setPage = (p: number) =>
    navigate({ to: "/profiles", search: (prev) => ({ ...prev, page: p }) })

  const profiles = data?.data ?? []
  const count = data?.count ?? 0

  if (isLoading) return <PendingProfiles />

  if (profiles.length === 0)
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSearch />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>No profiles yet</EmptyState.Title>
            <EmptyState.Description>
              Add a new profile to get started
            </EmptyState.Description>
          </VStack>
        </EmptyState.Content>
      </EmptyState.Root>
    )

  return (
    <>
      <Box
        borderWidth="1px"
        borderRadius="xl"
        overflow="hidden"
        bg="bg.panel"
        mt={6}
        shadow="sm"
      >
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
            {profiles.map((profile) => {
              const isExpanded = !!expandedRows[profile.id]
              const profileScripts =
                scriptsData?.data.filter((s) => s.profile_id === profile.id) ||
                []

              return (
                <Fragment key={profile.id}>
                  <Table.Row opacity={isPlaceholderData ? 0.5 : 1}>
                    <Table.Cell>
                      <Tooltip
                        content={
                          isExpanded
                            ? "Click to collapse"
                            : "Click to expand and view scripts"
                        }
                        showArrow
                        placement="right"
                      >
                        <IconButton
                          variant="ghost"
                          size="xs"
                          onClick={() => toggleRow(profile.id)}
                          aria-label="Expand profile scripts"
                        >
                          {isExpanded ? <FiChevronDown /> : <FiChevronRight />}
                        </IconButton>
                      </Tooltip>
                    </Table.Cell>
                    <Table.Cell fontWeight="medium" truncate>
                      {profile.name}
                    </Table.Cell>
                    <Table.Cell>
                      <Badge
                        colorPalette={profile.generate_config ? "green" : "red"}
                        variant="subtle"
                        size="sm"
                      >
                        {profile.generate_config ? "Yes" : "No"}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell>
                      <Badge
                        variant="subtle"
                        colorPalette={
                          profile.action === "permit" ? "green" : "orange"
                        }
                      >
                        {profile.action}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell
                      color={!profile.description ? "gray" : "inherit"}
                      truncate
                    >
                      {profile.description || "N/A"}
                    </Table.Cell>
                    <Table.Cell>
                      <ProfileActionsMenu profile={profile} />
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
                            Profile Script Structure ({profileScripts.length})
                          </Heading>
                          <AddProfileScript
                            profileId={profile.id}
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
                        {profileScripts.length === 0 ? (
                          <Text fontSize="sm" color="fg.muted" py={2}>
                            No scripts configured. Click "Add Script Block" to
                            get started.
                          </Text>
                        ) : (
                          <VStack align="stretch" gap={3} w="full">
                            {profileScripts.map((script) => {
                              const scriptSets =
                                scriptSetsData?.data.filter(
                                  (ss) => ss.profilescript_id === script.id,
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
                                      <EditProfileScript
                                        profilescript={script}
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
                                      <DeleteProfileScript
                                        profilescript={script}
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
                                      <VStack align="stretch" gap={1.5} mb={2}>
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
                                              <EditProfileScriptSet
                                                profilescriptset={set}
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
                                              <DeleteProfileScriptSet
                                                profilescriptset={set}
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
                                    <AddProfileScriptSet
                                      profilescriptId={script.id}
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
                                profile.action === "permit" ? "green" : "orange"
                              }
                              variant="solid"
                            >
                              {profile.action}
                            </Badge>
                            <Text
                              fontSize="xs"
                              color="fg.muted"
                              display="inline-flex"
                              alignItems="center"
                              gap={1}
                            >
                              (Applied if none of the script blocks above match
                              the request. Learn more in the{" "}
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
  )
}

// ── Page root ─────────────────────────────────────────────────────────────────

function Profiles() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleProfileSearch = (val: string) => {
    navigate({
      to: "/profiles",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <PageHeader
        title="Profiles Management"
        description="Profiles group service configurations, authorization instructions, and command permissions returned to network clients. Click the chevron (>) on any row to expand and view its script structure."
        icon={FiFileText}
      />
      <Flex mt={6} align="center" justify="space-between" gap={4} wrap="wrap">
        <HStack gap={3}>
          <AddProfile />
          <PreviewProfile />
        </HStack>
        <SearchBox
          initialValue={search}
          onSearch={handleProfileSearch}
          placeholder="Search by name, action, description..."
        />
      </Flex>

      <ProfilesTable />
    </Container>
  )
}
