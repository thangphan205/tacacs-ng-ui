import {
  Badge,
  Container,
  EmptyState,
  Flex,
  Heading,
  HStack,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { FiKey } from "react-icons/fi"

import { type ApiKeyPublic, ApiKeysService } from "@/client"
import { Tooltip } from "../ui/tooltip"
import AddApiKey from "./AddApiKey"
import EditApiKeyAllowedIps from "./EditApiKeyAllowedIps"
import RevokeApiKey from "./RevokeApiKey"

type KeyStatus = "Active" | "Revoked" | "Expired"

function statusOf(apiKey: ApiKeyPublic): KeyStatus {
  if (apiKey.revoked_at) return "Revoked"
  if (apiKey.expires_at && new Date(apiKey.expires_at) <= new Date()) {
    return "Expired"
  }
  return "Active"
}

const STATUS_COLOR: Record<KeyStatus, string> = {
  Active: "green",
  Revoked: "red",
  Expired: "orange",
}

function formatDate(value: string | null | undefined, fallback = "—") {
  if (!value) return fallback
  return new Date(value).toLocaleString("en-US", { hour12: false })
}

const ApiKeys = () => {
  const { data, isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => ApiKeysService.readApiKeys({ limit: 200 }),
  })

  const apiKeys = data?.data ?? []

  return (
    <Container maxW="full">
      <Flex
        align={{ base: "start", md: "center" }}
        justify="space-between"
        direction={{ base: "column", md: "row" }}
        gap={3}
        py={4}
      >
        <VStack align="start" gap={1}>
          <Heading size="sm">API Keys</Heading>
          <Text fontSize="sm" color="gray.500">
            Machine credentials for the read-only MCP server. They cannot sign
            in to this UI and cannot change any configuration.
          </Text>
        </VStack>
        <AddApiKey />
      </Flex>

      {!isLoading && apiKeys.length === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiKey />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>No API keys yet</EmptyState.Title>
              <EmptyState.Description>
                Create one to let an MCP client inspect TACACS+ configuration.
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <Table.Root size="sm" interactive>
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Name</Table.ColumnHeader>
              <Table.ColumnHeader>Prefix</Table.ColumnHeader>
              <Table.ColumnHeader>Scopes</Table.ColumnHeader>
              <Table.ColumnHeader>Allowed IPs</Table.ColumnHeader>
              <Table.ColumnHeader>Status</Table.ColumnHeader>
              <Table.ColumnHeader>Expires</Table.ColumnHeader>
              <Table.ColumnHeader>Last used</Table.ColumnHeader>
              <Table.ColumnHeader />
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {apiKeys.map((apiKey) => {
              const status = statusOf(apiKey)
              return (
                <Table.Row
                  key={apiKey.id}
                  opacity={status === "Active" ? 1 : 0.6}
                >
                  <Table.Cell>
                    <VStack align="start" gap={0}>
                      <Text>{apiKey.name}</Text>
                      {apiKey.description && (
                        <Text fontSize="xs" color="gray.500">
                          {apiKey.description}
                        </Text>
                      )}
                    </VStack>
                  </Table.Cell>
                  <Table.Cell fontFamily="mono" fontSize="xs">
                    {apiKey.key_prefix}…
                  </Table.Cell>
                  <Table.Cell>
                    <HStack gap={1} wrap="wrap">
                      {apiKey.scopes
                        ?.split(",")
                        .filter(Boolean)
                        .map((scope) => (
                          <Badge
                            key={scope}
                            size="sm"
                            variant="subtle"
                            colorPalette={
                              scope === "mcp:secrets" ? "orange" : "blue"
                            }
                          >
                            {scope}
                          </Badge>
                        ))}
                    </HStack>
                  </Table.Cell>
                  <Table.Cell fontSize="xs">
                    {(() => {
                      const ips =
                        apiKey.allowed_ips?.split(",").filter(Boolean) ?? []
                      if (ips.length === 0) {
                        return <Text color="gray.500">Any</Text>
                      }
                      const [first, ...rest] = ips
                      return (
                        <HStack gap={1}>
                          <Text fontFamily="mono">{first}</Text>
                          {rest.length > 0 && (
                            <Tooltip content={rest.join(", ")}>
                              <Text color="gray.500" cursor="default">
                                +{rest.length} more
                              </Text>
                            </Tooltip>
                          )}
                        </HStack>
                      )
                    })()}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={STATUS_COLOR[status]} variant="subtle">
                      {status}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell>
                    {formatDate(apiKey.expires_at, "Never")}
                  </Table.Cell>
                  <Table.Cell>
                    {formatDate(apiKey.last_used_at, "Never")}
                  </Table.Cell>
                  <Table.Cell textAlign="end">
                    {status !== "Revoked" && (
                      <HStack gap={1} justify="end">
                        <EditApiKeyAllowedIps apiKey={apiKey} />
                        <RevokeApiKey apiKey={apiKey} />
                      </HStack>
                    )}
                  </Table.Cell>
                </Table.Row>
              )
            })}
          </Table.Body>
        </Table.Root>
      )}
    </Container>
  )
}

export default ApiKeys
