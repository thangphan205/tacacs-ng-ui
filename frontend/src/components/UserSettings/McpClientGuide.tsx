import {
  Box,
  Clipboard,
  Code,
  HStack,
  IconButton,
  Tabs,
  Text,
  VStack,
} from "@chakra-ui/react"
import { FiCheck, FiCopy, FiInfo } from "react-icons/fi"

import { OpenAPI } from "@/client"

interface McpClientGuideProps {
  apiKey?: string
  showEndpointInfo?: boolean
}

export function getMcpEndpointUrl(): string {
  const base =
    OpenAPI.BASE ||
    (typeof window !== "undefined" ? window.location.origin : "")
  const cleanBase = base.replace(/\/+$/, "")
  return `${cleanBase}/mcp/`
}

export const McpClientGuide = ({
  apiKey,
  showEndpointInfo = true,
}: McpClientGuideProps) => {
  const keyText = apiKey || "YOUR_API_KEY"
  const mcpUrl = getMcpEndpointUrl()

  const claudeCodeCmd = `claude mcp add --transport http tacacs-ng ${mcpUrl} --header "Authorization: Bearer ${keyText}"`

  const claudeDesktopConfig = JSON.stringify(
    {
      mcpServers: {
        "tacacs-ng": {
          command: "npx",
          args: [
            "-y",
            "mcp-remote",
            mcpUrl,
            "--header",
            `Authorization: Bearer ${keyText}`,
          ],
        },
      },
    },
    null,
    2,
  )

  const antigravityConfig = JSON.stringify(
    {
      mcpServers: {
        "tacacs-ng": {
          command: "npx",
          args: [
            "-y",
            "mcp-remote",
            mcpUrl,
            "--header",
            `Authorization: Bearer ${keyText}`,
          ],
        },
      },
    },
    null,
    2,
  )

  const geminiCmd = `gemini mcp add tacacs-ng --url ${mcpUrl} --header "Authorization: Bearer ${keyText}"`

  const cursorConfig = JSON.stringify(
    {
      mcpServers: {
        "tacacs-ng": {
          command: "npx",
          args: [
            "-y",
            "mcp-remote",
            mcpUrl,
            "--header",
            `Authorization: Bearer ${keyText}`,
          ],
        },
      },
    },
    null,
    2,
  )

  return (
    <VStack align="stretch" gap={3} w="full">
      <Tabs.Root defaultValue="claude-code" variant="subtle" size="sm">
        <Tabs.List flexWrap="wrap" gap={1}>
          <Tabs.Trigger value="claude-code">Claude Code</Tabs.Trigger>
          <Tabs.Trigger value="claude-desktop">Claude Desktop</Tabs.Trigger>
          <Tabs.Trigger value="antigravity">Antigravity</Tabs.Trigger>
          <Tabs.Trigger value="gemini">Gemini</Tabs.Trigger>
          <Tabs.Trigger value="cursor">Cursor / Windsurf</Tabs.Trigger>
        </Tabs.List>

        {/* Claude Code */}
        <Tabs.Content value="claude-code">
          <VStack align="stretch" gap={2} pt={2}>
            <HStack justify="space-between" align="center">
              <Text fontSize="xs" color="gray.500">
                Run in your terminal to add the MCP server to Claude Code CLI:
              </Text>
              <Clipboard.Root value={claudeCodeCmd}>
                <Clipboard.Trigger asChild>
                  <IconButton
                    variant="subtle"
                    size="xs"
                    aria-label="Copy Claude Code command"
                  >
                    <Clipboard.Indicator copied={<FiCheck color="green" />}>
                      <FiCopy />
                    </Clipboard.Indicator>
                  </IconButton>
                </Clipboard.Trigger>
              </Clipboard.Root>
            </HStack>
            <Code
              p={3}
              borderRadius="md"
              fontSize="xs"
              wordBreak="break-all"
              whiteSpace="pre-wrap"
              display="block"
            >
              {claudeCodeCmd}
            </Code>
            <Text fontSize="xs" color="gray.500">
              💡 Surfaces the <Code fontSize="xs">author_tacacs_config</Code>{" "}
              workflow prompt and entity inspection tools.
            </Text>
          </VStack>
        </Tabs.Content>

        {/* Claude Desktop */}
        <Tabs.Content value="claude-desktop">
          <VStack align="stretch" gap={2} pt={2}>
            <HStack justify="space-between" align="center">
              <Text fontSize="xs" color="gray.500">
                Add to your{" "}
                <Code fontSize="xs">claude_desktop_config.json</Code>:
              </Text>
              <Clipboard.Root value={claudeDesktopConfig}>
                <Clipboard.Trigger asChild>
                  <IconButton
                    variant="subtle"
                    size="xs"
                    aria-label="Copy Claude Desktop config"
                  >
                    <Clipboard.Indicator copied={<FiCheck color="green" />}>
                      <FiCopy />
                    </Clipboard.Indicator>
                  </IconButton>
                </Clipboard.Trigger>
              </Clipboard.Root>
            </HStack>
            <Code
              p={3}
              borderRadius="md"
              fontSize="xs"
              wordBreak="break-all"
              whiteSpace="pre-wrap"
              display="block"
            >
              {claudeDesktopConfig}
            </Code>
            <VStack align="start" gap={0.5} fontSize="xs" color="gray.500">
              <Text>
                • <strong>macOS:</strong>{" "}
                <Code fontSize="xs">
                  ~/Library/Application
                  Support/Claude/claude_desktop_config.json
                </Code>
              </Text>
              <Text>
                • <strong>Windows:</strong>{" "}
                <Code fontSize="xs">
                  %APPDATA%\Claude\claude_desktop_config.json
                </Code>
              </Text>
              <Text>• Restart Claude Desktop after saving the file.</Text>
            </VStack>
          </VStack>
        </Tabs.Content>

        {/* Google Antigravity */}
        <Tabs.Content value="antigravity">
          <VStack align="stretch" gap={2} pt={2}>
            <HStack justify="space-between" align="center">
              <Text fontSize="xs" color="gray.500">
                Add to{" "}
                <Code fontSize="xs">~/.gemini/config/mcp_config.json</Code> or
                project <Code fontSize="xs">.agents/mcp_config.json</Code>:
              </Text>
              <Clipboard.Root value={antigravityConfig}>
                <Clipboard.Trigger asChild>
                  <IconButton
                    variant="subtle"
                    size="xs"
                    aria-label="Copy Antigravity MCP config"
                  >
                    <Clipboard.Indicator copied={<FiCheck color="green" />}>
                      <FiCopy />
                    </Clipboard.Indicator>
                  </IconButton>
                </Clipboard.Trigger>
              </Clipboard.Root>
            </HStack>
            <Code
              p={3}
              borderRadius="md"
              fontSize="xs"
              wordBreak="break-all"
              whiteSpace="pre-wrap"
              display="block"
            >
              {antigravityConfig}
            </Code>
            <Text fontSize="xs" color="gray.500">
              💡 Antigravity will discover the tools automatically. You can
              verify under{" "}
              <strong>Additional Options (...) → MCP Servers</strong>.
            </Text>
          </VStack>
        </Tabs.Content>

        {/* Gemini */}
        <Tabs.Content value="gemini">
          <VStack align="stretch" gap={2} pt={2}>
            <HStack justify="space-between" align="center">
              <Text fontSize="xs" color="gray.500">
                Run with Gemini CLI:
              </Text>
              <Clipboard.Root value={geminiCmd}>
                <Clipboard.Trigger asChild>
                  <IconButton
                    variant="subtle"
                    size="xs"
                    aria-label="Copy Gemini CLI command"
                  >
                    <Clipboard.Indicator copied={<FiCheck color="green" />}>
                      <FiCopy />
                    </Clipboard.Indicator>
                  </IconButton>
                </Clipboard.Trigger>
              </Clipboard.Root>
            </HStack>
            <Code
              p={3}
              borderRadius="md"
              fontSize="xs"
              wordBreak="break-all"
              whiteSpace="pre-wrap"
              display="block"
            >
              {geminiCmd}
            </Code>
            <Text fontSize="xs" color="gray.500">
              Or configure in <Code fontSize="xs">~/.gemini/settings.json</Code>{" "}
              using the same <Code fontSize="xs">mcpServers</Code> JSON schema
              as Antigravity.
            </Text>
          </VStack>
        </Tabs.Content>

        {/* Cursor / Windsurf */}
        <Tabs.Content value="cursor">
          <VStack align="stretch" gap={2} pt={2}>
            <HStack justify="space-between" align="center">
              <Text fontSize="xs" color="gray.500">
                Add to <Code fontSize="xs">.cursor/mcp.json</Code> or Cursor
                Settings → Features → MCP:
              </Text>
              <Clipboard.Root value={cursorConfig}>
                <Clipboard.Trigger asChild>
                  <IconButton
                    variant="subtle"
                    size="xs"
                    aria-label="Copy Cursor MCP config"
                  >
                    <Clipboard.Indicator copied={<FiCheck color="green" />}>
                      <FiCopy />
                    </Clipboard.Indicator>
                  </IconButton>
                </Clipboard.Trigger>
              </Clipboard.Root>
            </HStack>
            <Code
              p={3}
              borderRadius="md"
              fontSize="xs"
              wordBreak="break-all"
              whiteSpace="pre-wrap"
              display="block"
            >
              {cursorConfig}
            </Code>
            <Text fontSize="xs" color="gray.500">
              💡 Works with any MCP host that supports stdio commands via the{" "}
              <Code fontSize="xs">mcp-remote</Code> npm bridge.
            </Text>
          </VStack>
        </Tabs.Content>
      </Tabs.Root>

      {showEndpointInfo && (
        <HStack
          align="start"
          gap={2}
          p={2.5}
          borderRadius="md"
          bg="bg.muted"
          borderWidth="1px"
          borderColor="border.subtle"
        >
          <Box color="blue.500" pt={0.5}>
            <FiInfo fontSize="14px" />
          </Box>
          <Text fontSize="xs" color="gray.600">
            <strong>Endpoint:</strong> Canonical URL is{" "}
            <Code fontSize="xs">{mcpUrl}</Code> (trailing slash required;
            requires <Code fontSize="xs">MCP_ENABLED=true</Code>). A{" "}
            <Code fontSize="xs">mcp:write</Code> key lets an LLM edit TACACS+
            entities, but no key can activate a configuration or reload the
            daemon — you must generate and activate the config yourself on the
            TACACS Configs page.
          </Text>
        </HStack>
      )}
    </VStack>
  )
}

export default McpClientGuide
