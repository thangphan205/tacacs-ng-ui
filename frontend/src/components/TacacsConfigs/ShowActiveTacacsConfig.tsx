import { Button, Textarea } from "@chakra-ui/react"
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

const ShowActiveTacacsConfig = () => {
    const [isOpen, setIsOpen] = useState(false)

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
                    <Textarea
                        readOnly
                        value={activeConfigData?.data || "No preview available."}
                        rows={20}
                        fontFamily="monospace"
                    />
                </DialogBody>
                <DialogCloseTrigger />
            </DialogContent>
        </DialogRoot>
    )
}

export default ShowActiveTacacsConfig