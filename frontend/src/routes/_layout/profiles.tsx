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

import { ProfilesService } from "@/client"
import { ProfileActionsMenu } from "@/components/Common/ProfileActionsMenu"
import AddProfile from "@/components/Profiles/AddProfile"
import PendingProfiles from "@/components/Pending/PendingProfiles"
import PreviewProfile from "@/components/Profiles/PreviewProfile"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const profilesSearchSchema = z.object({
  page: z.number().catch(1),
})

const PER_PAGE = 5

function getProfilesQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      ProfilesService.readProfiles({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["profiles", { page }],
  }
}

export const Route = createFileRoute("/_layout/profiles")({
  component: Profiles,
  validateSearch: (search) => profilesSearchSchema.parse(search),
})

function ProfilesTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page } = Route.useSearch()

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getProfilesQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/profiles",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const profiles = data?.data.slice(0, PER_PAGE) ?? []
  const count = data?.count ?? 0

  if (isLoading) {
    return <PendingProfiles />
  }

  if (profiles.length === 0) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSearch />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>You don't have any profiles yet</EmptyState.Title>
            <EmptyState.Description>
              Add a new profile to get started
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
          {profiles?.map((profile) => (
            <Table.Row key={profile.id} opacity={isPlaceholderData ? 0.5 : 1}>
              <Table.Cell truncate maxW="sm">
                {profile.id}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {profile.name}
              </Table.Cell>
              <Table.Cell truncate maxW="sm">
                {profile.action}
              </Table.Cell>
              <Table.Cell
                color={!profile.description ? "gray" : "inherit"}
                truncate
                maxW="30%"
              >
                {profile.description || "N/A"}
              </Table.Cell>
              <Table.Cell>
                <ProfileActionsMenu profile={profile} />
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

function Profiles() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12}>
        Profiles Management
      </Heading>
      <Flex gap={2}>
        <AddProfile />
        <PreviewProfile />
      </Flex>
      <ProfilesTable />
    </Container>
  )
}
