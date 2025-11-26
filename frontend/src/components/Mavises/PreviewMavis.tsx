import {
    Button,
    CodeBlock,
    Spinner,
    Text,
    createShikiAdapter,
} from "@chakra-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { FiEye } from "react-icons/fi"

import { type ApiError, MavisesService } from "@/client"
import {
    DialogBody,
    DialogCloseTrigger,
    DialogContent,
    DialogHeader,
    DialogRoot,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { handleError } from "@/utils"
import type { HighlighterGeneric } from "shiki"
import { useColorMode } from "@/components/ui/color-mode"

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

export default function PreviewMavis() {
    const [isOpen, setIsOpen] = useState(false)
    const queryClient = useQueryClient()
    const { colorMode } = useColorMode()

    const { data: previewData, isLoading } = useQuery({
        queryKey: ["mavisPreview"],
        queryFn: () => MavisesService.previewMavis(),
        enabled: isOpen, // Only fetch when the modal is open
        staleTime: Infinity,
        gcTime: 0,
        meta: {
            onError: (err: ApiError) => {
                handleError(err)
            },
        },
    })

    const handlePreview = () => {
        queryClient.invalidateQueries({ queryKey: ["mavisPreview"] })
    }

    return (
        <DialogRoot
            size={{ base: "xs", md: "xl" }}
            open={isOpen}
            onOpenChange={({ open }) => setIsOpen(open)}
        >
            <DialogTrigger asChild>
                <Button
                    my={4}
                    onClick={handlePreview}
                    loading={isLoading && isOpen}
                >
                    <FiEye fontSize="16px" />
                    Preview Mavis
                </Button>
            </DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Preview Candidate Mavis Settings</DialogTitle>
                </DialogHeader>
                <DialogBody>
                    {isLoading ? (
                        <Spinner />
                    ) : previewData?.data ? (
                        <CodeBlock.AdapterProvider value={shikiAdapter}>
                            <CodeBlock.Root
                                code={previewData.data}
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
                        <Text>No preview available.</Text>
                    )}
                </DialogBody>
                <DialogCloseTrigger />
            </DialogContent>
        </DialogRoot>
    )
}