import {
  Badge,
  Box,
  Container,
  EmptyState,
  Flex,
  Heading,
  HStack,
  IconButton,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useState } from "react"
import {
  FiCheck,
  FiCopy,
  FiEye,
  FiEyeOff,
  FiKey,
  FiSearch,
} from "react-icons/fi"
import { z } from "zod"

import { MavisesService } from "@/client"
import { MavisActionsMenu } from "@/components/Common/MavisActionsMenu"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import { SearchBox } from "@/components/Common/SearchBox"
import AddMavis from "@/components/Mavises/AddMavis"
import LoadMavisTemplate from "@/components/Mavises/LoadMavisTemplate"
import PreviewMavis from "@/components/Mavises/PreviewMavis"
import PendingMavises from "@/components/Pending/PendingMavises"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination.tsx"

const mavisesSearchSchema = z.object({
  page: z.number().catch(1),
  search: z.string().optional(),
})

const DEFAULT_PER_PAGE = 5

function getMavisesQueryOptions({
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
      MavisesService.readMavises({
        skip: (page - 1) * perPage,
        limit: perPage,
        search,
      }),
    queryKey: ["mavises", { page, search, perPage }],
  }
}

export const Route = createFileRoute("/_layout/mavises")({
  component: Mavises,
  validateSearch: (search) => mavisesSearchSchema.parse(search),
})

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <IconButton
      variant="ghost"
      size="xs"
      onClick={handleCopy}
      aria-label="Copy ID"
      color="fg.muted"
      _hover={{ color: "teal.fg" }}
    >
      {copied ? <FiCheck color="green" /> : <FiCopy />}
    </IconButton>
  )
}

function ValueCell({
  mavisKey,
  mavisValue,
}: {
  mavisKey: string
  mavisValue: string
}) {
  const isSecret =
    mavisKey.toLowerCase().includes("passwd") ||
    mavisKey.toLowerCase().includes("password") ||
    mavisKey.toLowerCase().includes("secret") ||
    (mavisKey.toLowerCase().includes("key") &&
      !mavisKey.toUpperCase().endsWith("_KEY"))
  const [showSecret, setShowSecret] = useState(false)

  if (isSecret) {
    return (
      <HStack gap={2}>
        <Text fontFamily="mono" fontSize="sm">
          {showSecret ? mavisValue : "••••••••••••"}
        </Text>
        <IconButton
          variant="ghost"
          size="xs"
          onClick={() => setShowSecret(!showSecret)}
          aria-label={showSecret ? "Hide password" : "Show password"}
          color="fg.muted"
          _hover={{ color: "teal.fg" }}
        >
          {showSecret ? <FiEyeOff /> : <FiEye />}
        </IconButton>
      </HStack>
    )
  }

  return (
    <Text fontFamily="mono" fontSize="sm" truncate maxW="md">
      {mavisValue}
    </Text>
  )
}

function MavisesTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, search } = Route.useSearch()

  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading, isPlaceholderData } = useQuery({
    ...getMavisesQueryOptions({ page, search, perPage }),
    placeholderData: (prevData) => prevData,
  })

  const setPage = (page: number) => {
    navigate({
      to: "/mavises",
      search: (prev) => ({ ...prev, page }),
    })
  }

  const mavises = data?.data ?? []
  const count = data?.count ?? 0

  return (
    <>
      {isLoading ? (
        <PendingMavises />
      ) : mavises.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>
                You don't have any mavises yet
              </EmptyState.Title>
              <EmptyState.Description>
                Add a new mavis to get started
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Box
            borderWidth="1px"
            borderRadius="xl"
            overflow="hidden"
            bg="bg.panel"
            mt={6}
            shadow="sm"
          >
            <Table.Root size={{ base: "sm", md: "md" }}>
              <Table.Header bg="bg.muted">
                <Table.Row>
                  <Table.ColumnHeader w="xs">ID</Table.ColumnHeader>
                  <Table.ColumnHeader w="sm">Key</Table.ColumnHeader>
                  <Table.ColumnHeader w="md">Value</Table.ColumnHeader>
                  <Table.ColumnHeader w="20" textAlign="right">
                    Actions
                  </Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {mavises?.map((mavis) => (
                  <Table.Row
                    key={mavis.id}
                    opacity={isPlaceholderData ? 0.5 : 1}
                    _hover={{ bg: "bg.muted/50" }}
                    transition="background 0.2s"
                  >
                    <Table.Cell>
                      <HStack gap={2}>
                        <Text fontFamily="mono" fontSize="xs" color="fg.muted">
                          {mavis.id.substring(0, 8)}...
                        </Text>
                        <CopyButton text={mavis.id} />
                      </HStack>
                    </Table.Cell>
                    <Table.Cell>
                      <Badge
                        variant="subtle"
                        colorPalette="teal"
                        fontFamily="mono"
                        size="md"
                        px={2}
                        py={0.5}
                      >
                        {mavis.mavis_key}
                      </Badge>
                    </Table.Cell>
                    <Table.Cell>
                      <ValueCell
                        mavisKey={mavis.mavis_key}
                        mavisValue={mavis.mavis_value}
                      />
                    </Table.Cell>
                    <Table.Cell textAlign="right">
                      <MavisActionsMenu mavis={mavis} />
                    </Table.Cell>
                  </Table.Row>
                ))}
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

function Mavises() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { search } = Route.useSearch()

  const handleSearch = (val: string) => {
    navigate({
      to: "/mavises",
      search: (prev) => ({ ...prev, page: 1, search: val || undefined }),
    })
  }

  return (
    <Container maxW="full">
      <Flex direction="column" pt={6} gap={1}>
        <HStack gap={3}>
          <Box p={2} bg="teal.muted" borderRadius="lg" color="teal.fg">
            <FiKey fontSize="22px" />
          </Box>
          <VStack align="start" gap={0}>
            <Heading size="md">Mavis Backend Configurations</Heading>
            <Text color="fg.muted" fontSize="xs">
              Configure and map key-value environment variables for external
              authentication backends, such as LDAP, Active Directory, and
              custom MAVIS modules.
            </Text>
          </VStack>
        </HStack>
      </Flex>
      <Flex mt={6} align="center" justify="space-between" gap={4} wrap="wrap">
        <HStack gap={3}>
          <AddMavis />
          <LoadMavisTemplate />
          <PreviewMavis />
        </HStack>
        <SearchBox
          initialValue={search}
          onSearch={handleSearch}
          placeholder="Search by key, value..."
        />
      </Flex>
      <MavisesTable />
    </Container>
  )
}
