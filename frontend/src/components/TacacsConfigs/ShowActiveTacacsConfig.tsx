import {
    Button,
    CodeBlock,
    Spinner,
    Text,
    createShikiAdapter,
} from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { FiShield } from "react-icons/fi"

import { type ApiError, TacacsConfigsService } from "@/client"
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

const ShowActiveTacacsConfig = () => {
    const [isOpen, setIsOpen] = useState(false)
    const { colorMode } = useColorMode()

    const { data: activeConfigData, isLoading } = useQuery({
        queryKey: ["activeTacacsConfig"],
        queryFn: () => TacacsConfigsService.getActiveTacacsConfig(),
        enabled: isOpen, // Only fetch when the modal is open
        meta: {
            onError: (err: ApiError) => {
                handleError(err)
            },
        },
    })

    return (
        <DialogRoot
            size={{ base: "xs", md: "xl" }}
            open={isOpen}
            onOpenChange={({ open }) => setIsOpen(open)}
        >
            <DialogTrigger asChild>
                <Button my={4} loading={isLoading && isOpen}>
                    <FiShield fontSize="16px" />
                    Show Active Config
                </Button>
            </DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Active TACACS+ Config, Created At: {activeConfigData?.created_at ? new Date(activeConfigData.created_at).toLocaleString() : "N/A"}</DialogTitle>
                </DialogHeader>
                <DialogBody colorPalette={"green"}>
                    {isLoading ? (
                        <Spinner />
                    ) : activeConfigData?.data ? (
                        <CodeBlock.AdapterProvider value={shikiAdapter}>
                            <CodeBlock.Root
                                code={activeConfigData.data}
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
                        <Text>No active configuration found.</Text>
                    )}
                </DialogBody>
                <DialogCloseTrigger />
            </DialogContent>
        </DialogRoot>
    )
}

export default ShowActiveTacacsConfig