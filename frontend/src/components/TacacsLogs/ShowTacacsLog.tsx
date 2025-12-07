import {
  Button,
  ButtonGroup,
  CodeBlock,
  Group,
  Input,
  Spinner,
  Text,
  createShikiAdapter,
  IconButton
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { FaEye } from "react-icons/fa"
import React from "react"
import {
  TacacsLogsService,
} from "@/client"
import type { HighlighterGeneric } from "shiki"
import { useColorMode } from "@/components/ui/color-mode"


import {
  DialogActionTrigger,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog"

interface ShowTacacsLogProps {
  tacacs_log: any
  children?: React.ReactNode
}

const shikiAdapter = createShikiAdapter<HighlighterGeneric<any, any>>({
  async load() {
    const { createHighlighter } = await import("shiki")
    return createHighlighter({
      langs: ["log"],
      themes: ["github-dark", "github-light"],
    })
  },
  theme: {
    light: "github-light",
    dark: "github-dark",
  },
})

const ShowTacacsLog = ({
  tacacs_log,
  children,
}: ShowTacacsLogProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const { colorMode } = useColorMode()
  // This state will hold the value from the input field
  const [searchTerm, setSearchTerm] = useState("")
  // This state will hold the term that is actually submitted for searching
  const [submittedSearchTerm, setSubmittedSearchTerm] = useState("")

  const { data, isLoading, error } = useQuery({
    // The submitted search term is added to the query key to trigger a refetch only when it changes
    queryKey: ["tacacs_log", tacacs_log.id, submittedSearchTerm],
    queryFn: () =>
      TacacsLogsService.readLogFile({
        id: tacacs_log.id,
        search: submittedSearchTerm || undefined, // Pass undefined if search is empty
      }),
    enabled: isOpen, // Only fetch when the dialog is open
    // Adding a small staleTime to prevent refetching on window focus
    staleTime: 1000 * 60, // 1 minute
  })

  const renderContent = () => {
    if (isLoading) {
      return <Spinner />
    }
    if (error) {
      return <Text color="red.500">Error loading configuration.</Text>
    }
    if (data?.data) {
      return (
        <CodeBlock.AdapterProvider value={shikiAdapter}>
          <CodeBlock.Root
            code={data.data}
            language="log"
            meta={{ showLineNumbers: true, colorScheme: colorMode }}
            maxLines={20}
          >
            <CodeBlock.Header>
              <CodeBlock.Control>
                <CodeBlock.CollapseTrigger asChild>
                  <IconButton variant="solid" size="sm">
                    <CodeBlock.CollapseIndicator />
                  </IconButton>
                </CodeBlock.CollapseTrigger>
                <CodeBlock.CopyTrigger asChild>
                  <IconButton variant="solid" size="sm">
                    <CodeBlock.CopyIndicator />
                  </IconButton>
                </CodeBlock.CopyTrigger>
              </CodeBlock.Control>
            </CodeBlock.Header>
            <CodeBlock.Content>
              <CodeBlock.Code>
                <CodeBlock.CodeText />
              </CodeBlock.Code>
              <CodeBlock.Overlay>
                <CodeBlock.CollapseTrigger>
                  <CodeBlock.CollapseText textStyle="sm" />
                </CodeBlock.CollapseTrigger>
              </CodeBlock.Overlay>
            </CodeBlock.Content>
          </CodeBlock.Root>
        </CodeBlock.AdapterProvider>
      )
    }

    return <Text>No content available.</Text>
  }

  const handleSearch = () => {
    setSubmittedSearchTerm(searchTerm)
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      handleSearch()
    }
  }

  return (
    <DialogRoot
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        {children || (
          <Button variant="ghost" size="sm">
            <FaEye fontSize="16px" />
            Show Config
          </Button>
        )}
      </DialogTrigger>
      <DialogContent w="80vw" maxW="80vw" h="80vh" maxH="80vh">
        <DialogHeader>
          <DialogTitle>
            Log for: {tacacs_log.filename}
          </DialogTitle>
        </DialogHeader>
        <DialogBody display="flex" flexDirection="column" gap={4} maxLines={30}>
          <Group attached w="full" maxW="md">
            <Input
              placeholder="Search in log content..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <Button onClick={handleSearch} variant="solid" >Search</Button>
          </Group>
          {renderContent()}
        </DialogBody>
        <DialogFooter gap={2}>
          <ButtonGroup>
            <DialogActionTrigger asChild>
              <Button
                variant="subtle"
                colorPalette="gray"
              >
                Cancel
              </Button>
            </DialogActionTrigger>
          </ButtonGroup>
        </DialogFooter>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot >
  )
}

export default ShowTacacsLog
