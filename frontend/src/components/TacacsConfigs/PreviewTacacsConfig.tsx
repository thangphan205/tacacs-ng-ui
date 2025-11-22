import { Button, Textarea } from "@chakra-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { FiEye } from "react-icons/fi"

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

const PreviewTacacsConfig = () => {
    const [isOpen, setIsOpen] = useState(false)
    const queryClient = useQueryClient()

    const { data: previewData, isLoading } = useQuery({
        queryKey: ["tacacsConfigPreview"],
        queryFn: () => TacacsConfigsService.generatePreviewTacacsConfig(),
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
        queryClient.invalidateQueries({ queryKey: ["tacacsConfigPreview"] })
    }

    return (
        <DialogRoot
            size={{ base: "xs", md: "xl" }}
            open={isOpen}
            onOpenChange={({ open }) => setIsOpen(open)}
        >
            <DialogTrigger asChild>
                <Button my={4} onClick={handlePreview} loading={isLoading && isOpen}>
                    <FiEye fontSize="16px" />
                    Preview Candidate Add TacacsConfig
                </Button>
            </DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Preview Candidate TACACS+ Config</DialogTitle>
                </DialogHeader>
                <DialogBody>
                    <Textarea
                        readOnly
                        value={previewData?.data || "No preview available."}
                        rows={20}
                        fontFamily="monospace"
                    />
                </DialogBody>
                <DialogCloseTrigger />
            </DialogContent>
        </DialogRoot>
    )
}

export default PreviewTacacsConfig