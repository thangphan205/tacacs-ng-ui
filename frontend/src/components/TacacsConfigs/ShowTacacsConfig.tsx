import {
  Alert,
  Box,
  Button,
  ButtonGroup,
  CodeBlock,
  createShikiAdapter,
  Spinner,
  Text,
  Textarea,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type React from "react"
import { useEffect, useState } from "react"
import { FaCopy, FaDownload, FaEdit, FaEye, FaSave } from "react-icons/fa"
import type { HighlighterGeneric } from "shiki"
import {
  type ApiError,
  type TacacsConfigPublic,
  TacacsConfigsService,
  type TacacsConfigUpdate,
} from "@/client"
import { useColorMode } from "@/components/ui/color-mode"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
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

interface ShowTacacsConfigProps {
  tacacs_config: TacacsConfigPublic
  children?: React.ReactNode
}

interface CheckTacacsConfigProps {
  status: string
  raw_output: string
  line: number
  message: string
}

const shikiAdapter = createShikiAdapter<HighlighterGeneric<any, any>>({
  async load() {
    const { createHighlighter } = await import("shiki")
    return createHighlighter({
      langs: ["bash"],
      themes: ["github-dark", "github-light"],
    })
  },
  theme: {
    light: "github-light",
    dark: "github-dark",
  },
})

const ShowTacacsConfig = ({
  tacacs_config,
  children,
}: ShowTacacsConfigProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const { colorMode } = useColorMode()
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)
  const [editedContent, setEditedContent] = useState("")
  const [checkResult, setCheckResult] = useState<CheckTacacsConfigProps>({
    status: "",
    raw_output: "",
    line: -1,
    message: "",
  })
  const { showSuccessToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (data: TacacsConfigUpdate) =>
      TacacsConfigsService.updateTacacsConfig({
        id: tacacs_config.id,
        requestBody: data,
      }),
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tacacs_configs"] })
      queryClient.invalidateQueries({
        queryKey: ["tacacs_config", tacacs_config.id],
      })
    },
  })

  const mutation2 = useMutation<CheckTacacsConfigProps, ApiError>({
    mutationFn: () =>
      TacacsConfigsService.checkTacacsConfigById({
        id: tacacs_config.id,
      }) as Promise<CheckTacacsConfigProps>,
    onSuccess: (data) => {
      setCheckResult(data)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tacacs_configs"] })
    },
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ["tacacs_config", tacacs_config.id],
    queryFn: () =>
      TacacsConfigsService.readTacacsConfigById({ id: tacacs_config.id }),
    enabled: isOpen, // Only fetch when the dialog is open
  })

  useEffect(() => {
    if (data?.data) {
      setEditedContent(data.data)
    }
  }, [data?.data])

  const onActivate = () => {
    mutation.mutate(
      { filename: tacacs_config.filename, active: true },
      {
        onSuccess: () => {
          showSuccessToast("TacacsConfig activated successfully.")
          setIsOpen(false)
        },
      },
    )
  }

  const onSave = () => {
    mutation.mutate(
      { filename: tacacs_config.filename, data: editedContent, active: false },
      {
        onSuccess: () => {
          showSuccessToast("Configuration changes saved successfully.")
          setIsEditing(false)
        },
      },
    )
  }

  const onCheck = () => {
    mutation2.mutate()
  }

  const onDownload = () => {
    const content = editedContent || data?.data || ""
    const element = document.createElement("a")
    const file = new Blob([content], { type: "text/plain" })
    element.href = URL.createObjectURL(file)
    element.download = `${tacacs_config.filename}.cfg`
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
  }

  const getCorrectedLineNumber = () => {
    if (!checkResult.message || checkResult.line <= 0 || !editedContent) {
      return checkResult.line
    }
    const match = checkResult.message.match(/['"]([^'"]+)['"]/)
    if (match) {
      const token = match[1]
      const lines = editedContent.split("\n")
      const foundIndex = lines.findIndex((line) => line.includes(token))
      if (foundIndex !== -1) {
        return foundIndex + 1 // 1-indexed
      }
    }
    return checkResult.line
  }

  const correctedLine = getCorrectedLineNumber()

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    showSuccessToast("Error message copied to clipboard.")
  }

  return (
    <DialogRoot
      size={{ base: "xl", md: "xl" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => {
        setIsOpen(open)
        if (!open) {
          setIsEditing(false)
        }
      }}
    >
      <DialogTrigger asChild>
        {children || (
          <Button variant="ghost">
            <FaEye fontSize="16px" />
            Show Config
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Configuration for: {tacacs_config.filename}</DialogTitle>
        </DialogHeader>
        <DialogBody>
          {isLoading ? (
            <Spinner />
          ) : error ? (
            <Text color="red.500">Error loading configuration.</Text>
          ) : isEditing ? (
            <Textarea
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              fontFamily="mono"
              fontSize="sm"
              height="350px"
              maxH="400px"
              bg={colorMode === "dark" ? "gray.950" : "gray.50"}
              color={colorMode === "dark" ? "gray.100" : "gray.900"}
              borderColor={colorMode === "dark" ? "gray.800" : "gray.300"}
              p={3}
              borderRadius="md"
            />
          ) : data?.data ? (
            <CodeBlock.AdapterProvider value={shikiAdapter}>
              <CodeBlock.Root
                key={checkResult.line}
                code={data.data}
                language="bash"
                meta={{ showLineNumbers: true, colorScheme: colorMode }}
                maxH="400px"
                overflowY="auto"
              >
                <CodeBlock.Content>
                  <CodeBlock.Code>
                    <CodeBlock.CodeText />
                  </CodeBlock.Code>
                </CodeBlock.Content>
              </CodeBlock.Root>
            </CodeBlock.AdapterProvider>
          ) : (
            <Text>No content available.</Text>
          )}
          {checkResult.status && (
            <Box p={2}>
              <Alert.Root
                status={checkResult.status === "success" ? "success" : "error"}
                borderRadius="md"
                variant="subtle"
                w="full"
              >
                <Alert.Indicator />
                <Alert.Content>
                  {correctedLine > 0 && (
                    <Alert.Title mb={1}>
                      {checkResult.status === "success"
                        ? "Success"
                        : `Error Line: ${correctedLine}`}
                      {checkResult.status !== "success" &&
                        correctedLine !== checkResult.line &&
                        ` (detected at block start: ${checkResult.line})`}
                    </Alert.Title>
                  )}
                  <Box
                    display="flex"
                    justifyContent="space-between"
                    alignItems="start"
                    gap={2}
                    mt={1}
                  >
                    <Alert.Description
                      flex="1"
                      whiteSpace="normal"
                      wordBreak="break-word"
                      userSelect="text"
                      fontSize="sm"
                      fontFamily="mono"
                    >
                      {checkResult.message}
                    </Alert.Description>
                    {checkResult.status !== "success" && (
                      <Button
                        size="xs"
                        variant="subtle"
                        colorPalette="red"
                        onClick={() => copyToClipboard(checkResult.message)}
                        flexShrink={0}
                      >
                        <FaCopy />
                        Copy
                      </Button>
                    )}
                  </Box>
                </Alert.Content>
              </Alert.Root>
            </Box>
          )}
        </DialogBody>
        <DialogFooter gap={2}>
          <ButtonGroup>
            <DialogActionTrigger asChild>
              <Button
                variant="subtle"
                colorPalette="gray"
                disabled={mutation.isPending}
              >
                Cancel
              </Button>
            </DialogActionTrigger>
            {isEditing ? (
              <>
                <Button
                  variant="subtle"
                  onClick={() => {
                    setIsEditing(false)
                    setEditedContent(data?.data || "")
                  }}
                  disabled={mutation.isPending}
                >
                  Cancel Edit
                </Button>
                <Button
                  variant="solid"
                  onClick={onSave}
                  loading={mutation.isPending}
                >
                  <FaSave />
                  Save
                </Button>
              </>
            ) : (
              <>
                <Button variant="subtle" onClick={onDownload}>
                  <FaDownload />
                  Download
                </Button>
                <Button variant="subtle" onClick={() => setIsEditing(true)}>
                  <FaEdit />
                  Edit
                </Button>
                <Button
                  variant="solid"
                  onClick={onCheck}
                  loading={mutation2.isPending}
                >
                  Config Check
                </Button>
                <Button
                  variant="solid"
                  colorPalette="teal"
                  onClick={onActivate}
                  loading={mutation.isPending}
                  disabled={tacacs_config.active}
                >
                  {tacacs_config.active ? "Already Active" : "Activate"}
                </Button>
              </>
            )}
          </ButtonGroup>
        </DialogFooter>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default ShowTacacsConfig
