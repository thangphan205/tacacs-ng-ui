import { Badge, Button, DialogTitle, Text, VStack } from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { FiSlash } from "react-icons/fi"

import { type ApiKeyPublic, ApiKeysService } from "@/client"
import type { ApiError } from "@/client/core/ApiError"
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
  DialogTrigger,
} from "../ui/dialog"

const RevokeApiKey = ({ apiKey }: { apiKey: ApiKeyPublic }) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    handleSubmit,
    formState: { isSubmitting },
  } = useForm()

  const mutation = useMutation({
    mutationFn: () => ApiKeysService.revokeApiKey({ id: apiKey.id }),
    onSuccess: () => {
      showSuccessToast("API key revoked. It stops authenticating immediately.")
      setIsOpen(false)
    },
    onError: (err: ApiError) => handleError(err),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    },
  })

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      role="alertdialog"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost" size="xs" colorPalette="red">
          <FiSlash fontSize="14px" />
          Revoke
        </Button>
      </DialogTrigger>

      <DialogContent>
        <form onSubmit={handleSubmit(() => mutation.mutate())}>
          <DialogCloseTrigger />
          <DialogHeader>
            <DialogTitle>Revoke API Key</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <VStack align="start" gap={3}>
              <Badge colorPalette="red" variant="solid">
                {apiKey.name}
              </Badge>
              <Text fontSize="sm" fontFamily="mono" color="gray.500">
                {apiKey.key_prefix}…
              </Text>
              <Text>
                Any MCP client using this key stops working immediately. The row
                is kept so audit entries referencing it stay resolvable, but the
                key can never be re-enabled.
              </Text>
            </VStack>
          </DialogBody>

          <DialogFooter gap={2}>
            <DialogActionTrigger asChild>
              <Button
                variant="subtle"
                colorPalette="gray"
                disabled={isSubmitting}
              >
                Cancel
              </Button>
            </DialogActionTrigger>
            <Button
              variant="solid"
              colorPalette="red"
              type="submit"
              loading={isSubmitting}
            >
              Revoke
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </DialogRoot>
  )
}

export default RevokeApiKey
