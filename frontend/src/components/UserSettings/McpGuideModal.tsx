import {
  Badge,
  Box,
  Button,
  Code,
  DialogTitle,
  HStack,
  SimpleGrid,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useState } from "react"
import { FiBookOpen, FiCheckCircle, FiLock, FiShield } from "react-icons/fi"

import {
  DialogActionTrigger,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTrigger,
} from "../ui/dialog"
import McpClientGuide from "./McpClientGuide"

const TOOLS_SUMMARY = [
  {
    name: "whoami",
    scope: "—",
    desc: "Key identity, scopes and node role",
  },
  {
    name: "list_entities",
    scope: "mcp:read",
    desc: "List hosts, users, groups, profiles, rulesets, MAVIS, services",
  },
  {
    name: "describe_entity",
    scope: "mcp:read",
    desc: "Inspect entity details with nested scripts",
  },
  {
    name: "generate_config_preview",
    scope: "mcp:generate",
    desc: "Render full tac_plus-ng config preview from DB",
  },
  {
    name: "validate_config_text",
    scope: "mcp:validate",
    desc: "Syntax-check arbitrary config with tac_plus-ng -P (superuser only)",
  },
  {
    name: "validate_generated_config",
    scope: "mcp:validate",
    desc: "Validate real unredacted config server-side",
  },
  {
    name: "diff_generated_vs_active",
    scope: "mcp:generate",
    desc: "Unified diff between generated and active config",
  },
]

export const McpGuideModal = () => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <DialogRoot
      size={{ base: "xs", md: "lg", lg: "xl" }}
      placement="center"
      scrollBehavior="inside"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <FiBookOpen fontSize="16px" />
          MCP Setup Guide
        </Button>
      </DialogTrigger>

      <DialogContent maxH="85vh">
        <DialogCloseTrigger />
        <DialogHeader>
          <DialogTitle>MCP Client Setup Guide</DialogTitle>
        </DialogHeader>

        <DialogBody>
          <VStack align="stretch" gap={5}>
            <Text fontSize="sm" color="gray.600">
              The TACACS+ NG UI provides a Model Context Protocol (MCP) server
              allowing LLMs (Claude, Google Antigravity, Gemini, Cursor) to
              inspect configurations, draft changes, and syntax-validate
              tac_plus-ng configs. A read-write key additionally lets them edit
              TACACS+ entities — but never deploy them.
            </Text>

            <SimpleGrid columns={{ base: 1, md: 2 }} gap={3}>
              <Box
                p={3.5}
                borderRadius="md"
                borderWidth="1px"
                borderColor="green.500/30"
                bg="green.500/5"
              >
                <HStack gap={2} mb={2}>
                  <Box color="green.500">
                    <FiCheckCircle fontSize="16px" />
                  </Box>
                  <Text fontSize="xs" fontWeight="bold" color="green.600">
                    What API Keys CAN Do
                  </Text>
                </HStack>
                <VStack align="start" gap={1.5} fontSize="xs" color="gray.600">
                  <Text>
                    ✓ Inspect hosts, users, groups, profiles, rulesets &
                    settings
                  </Text>
                  <Text>
                    ✓ Render config previews and section snippets in memory
                  </Text>
                  <Text>
                    ✓ Compute unified diffs between database and active config
                  </Text>
                  <Text>
                    ✓ Run <Code fontSize="2xs">tac_plus-ng -P</Code> syntax
                    validation
                  </Text>
                  <Text>
                    ✓ With <Code fontSize="2xs">mcp:write</Code>: create, update
                    and delete entities in the database
                  </Text>
                </VStack>
              </Box>

              <Box
                p={3.5}
                borderRadius="md"
                borderWidth="1px"
                borderColor="orange.500/30"
                bg="orange.500/5"
              >
                <HStack gap={2} mb={2}>
                  <Box color="orange.500">
                    <FiShield fontSize="16px" />
                  </Box>
                  <Text fontSize="xs" fontWeight="bold" color="orange.600">
                    Guardrails (What It CANNOT Do)
                  </Text>
                </HStack>
                <VStack align="start" gap={1.5} fontSize="xs" color="gray.600">
                  <Text>
                    ✗ <strong>Cannot generate</strong> or save a config file
                  </Text>
                  <Text>
                    ✗ <strong>Cannot activate</strong> or deploy new
                    configurations
                  </Text>
                  <Text>
                    ✗ <strong>Cannot restart or reload</strong> the TACACS+
                    daemon
                  </Text>
                  <Text>
                    ✗ <strong>Cannot trigger HA sync</strong> to replica nodes
                  </Text>
                </VStack>
              </Box>
            </SimpleGrid>

            <Box
              p={3}
              borderRadius="md"
              bg="bg.muted"
              borderWidth="1px"
              borderColor="border.subtle"
            >
              <HStack align="start" gap={2}>
                <Box color="blue.500" pt={0.5}>
                  <FiLock fontSize="14px" />
                </Box>
                <Text fontSize="xs" color="gray.600">
                  <strong>Human-in-the-loop safety:</strong> MCP clients cannot
                  push changes to network devices. Even a read-write key only
                  edits database rows — the running daemon keeps serving the
                  currently active config. Deploying remains a deliberate human
                  action in this Web UI (
                  <strong>Configurations → Generate &amp; Activate</strong>).
                </Text>
              </HStack>
            </Box>

            <Box>
              <Text fontSize="sm" fontWeight="bold" mb={2}>
                Client Configuration
              </Text>
              <McpClientGuide />
            </Box>

            <Box>
              <Text fontSize="sm" fontWeight="bold" mb={2}>
                Available MCP Tools
              </Text>
              <Table.Root size="sm" variant="outline">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>Tool</Table.ColumnHeader>
                    <Table.ColumnHeader>Scope</Table.ColumnHeader>
                    <Table.ColumnHeader>Description</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {TOOLS_SUMMARY.map((t) => (
                    <Table.Row key={t.name}>
                      <Table.Cell fontFamily="mono" fontSize="xs">
                        {t.name}
                      </Table.Cell>
                      <Table.Cell>
                        {t.scope === "—" ? (
                          <Text fontSize="xs" color="gray.500">
                            —
                          </Text>
                        ) : (
                          <Badge
                            size="sm"
                            variant="subtle"
                            colorPalette={
                              t.scope.includes("secrets") ? "orange" : "blue"
                            }
                          >
                            {t.scope}
                          </Badge>
                        )}
                      </Table.Cell>
                      <Table.Cell fontSize="xs">{t.desc}</Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Box>
          </VStack>
        </DialogBody>

        <DialogFooter gap={2}>
          <DialogActionTrigger asChild>
            <Button variant="subtle" onClick={() => setIsOpen(false)}>
              Close
            </Button>
          </DialogActionTrigger>
        </DialogFooter>
      </DialogContent>
    </DialogRoot>
  )
}

export default McpGuideModal
