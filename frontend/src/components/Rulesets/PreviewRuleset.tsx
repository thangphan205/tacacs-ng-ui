import { Button, Textarea, VStack } from "@chakra-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { FiEye } from "react-icons/fi"

import { RulesetsService } from "@/client"
import {
    DialogBody,
    DialogCloseTrigger,
    DialogContent,
    DialogHeader,
    DialogRoot,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"


interface PreviewResponse {
    data: string;
}

const PreviewRuleset = () => {
    const [isOpen, setIsOpen] = useState(false)
    const queryClient = useQueryClient()

    const { data: previewData, isLoading } = useQuery<PreviewResponse>({
        queryKey: ["rulesetPreview"],
        queryFn: async () => await RulesetsService.previewRulesets() as PreviewResponse,
        enabled: isOpen, // Only fetch when the modal is open
    })

    const handlePreview = () => {
        queryClient.invalidateQueries({ queryKey: ["rulesetPreview"] })
    }

    return (
        <DialogRoot
            size={{ base: "md", md: "xl" }}
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
                    Preview Ruleset
                </Button>
            </DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Preview Candidate Ruleset</DialogTitle>
                </DialogHeader>
                <DialogBody>
                    <VStack>
                        {isLoading ? (
                            <p>Loading...</p>
                        ) : (
                            <Textarea
                                readOnly
                                value={previewData?.data || "No preview available."}
                                rows={20}
                                fontFamily="monospace"
                            />
                        )}
                    </VStack>
                </DialogBody>
                <DialogCloseTrigger />
            </DialogContent>
        </DialogRoot>
    )
}

export default PreviewRuleset