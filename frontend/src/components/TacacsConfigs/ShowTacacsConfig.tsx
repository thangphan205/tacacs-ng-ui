import {
  Badge,
  Button,
  ButtonGroup,
  Box,
  Spinner,
  Text,
  VStack,
  createShikiAdapter,
  CodeBlock
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { FaEye } from "react-icons/fa"
import React from "react"
import {
  type ApiError,
  type TacacsConfigPublic,
  type TacacsConfigUpdate,
  TacacsConfigsService,
} from "@/client"
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
} from "../ui/dialog";
import type { HighlighterGeneric } from "shiki"
import { useColorMode } from "@/components/ui/color-mode"


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
  const [checkResult, setCheckResult] = useState<CheckTacacsConfigProps>({ status: "", raw_output: "", line: -1, message: "" })
  const { showSuccessToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (data: TacacsConfigUpdate) =>
      TacacsConfigsService.updateTacacsConfig({
        id: tacacs_config.id,
        requestBody: data,
      }),
    onSuccess: () => {
      showSuccessToast("TacacsConfig activated successfully.")
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tacacs_configs"] })
    },
  })

  const mutation2 = useMutation<CheckTacacsConfigProps, ApiError>({
    mutationFn: () =>
      TacacsConfigsService.checkTacacsConfigById({ // This service call returns `unknown`
        id: tacacs_config.id
      }) as Promise<CheckTacacsConfigProps>, // We cast it to the correct type
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
    queryFn: () => TacacsConfigsService.readTacacsConfigById({ id: tacacs_config.id }),
    enabled: isOpen, // Only fetch when the dialog is open
  })

  const onActivate = () => {
    // We only need to send the filename, as the backend will handle the activation logic.
    // The description is optional.
    const { filename, description } = tacacs_config
    mutation.mutate({ filename, description })
  }
  const onCheck = () => {
    mutation2.mutate()
  }


  return (
    <DialogRoot
      size={{ base: "xl", md: "xl" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
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
          <DialogTitle>
            Configuration for: {tacacs_config.filename}
          </DialogTitle>
        </DialogHeader>
        <DialogBody>
          {isLoading ? (
            <Spinner />
          ) : error ? (
            <Text color="red.500">Error loading configuration.</Text>
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
          {checkResult.line > -1 && (
            <Box p={2}>
              <Badge colorPalette={checkResult.line === 0 ? "green" : "red"} variant="solid" w="full" p={2} borderRadius="md">
                <VStack align="start">
                  <Text textStyle="md">Error Line: {checkResult.line}</Text>
                  <Text textStyle="md">Message: {checkResult.message}</Text>
                </VStack>
              </Badge>
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
            <Button
              variant="solid"
              onClick={onActivate}
              loading={mutation.isPending}
              disabled={tacacs_config.active}
            >
              {tacacs_config.active ? "Already Active" : "Activate"}
            </Button>
            <Button
              variant="solid"
              onClick={onCheck}
              loading={mutation.isPending}
            >
              Config Check
            </Button>
          </ButtonGroup>
        </DialogFooter>
        <DialogCloseTrigger />


      </DialogContent>
    </DialogRoot>
  )
}

export default ShowTacacsConfig
