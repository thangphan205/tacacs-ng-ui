import { Badge, Button, DialogTitle, Text } from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { FiTrash2 } from "react-icons/fi"
import type { ApiError } from "@/api"
import { type RulesetScriptPublic, RulesetscriptsService } from "@/client"
import {
  DialogActionTrigger,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTrigger,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface DeleteRulesetScriptProps {
  rulesetscript: RulesetScriptPublic
  buttonElement?: React.ReactElement
}

const DeleteRulesetScript = ({
  rulesetscript,
  buttonElement,
}: DeleteRulesetScriptProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    handleSubmit,
    formState: { isSubmitting },
  } = useForm()

  const deleteRulesetScript = async (id: string) => {
    await RulesetscriptsService.deleteRulesetscript({ id: id })
  }

  const mutation = useMutation({
    mutationFn: deleteRulesetScript,
    onSuccess: () => {
      showSuccessToast("The item was deleted successfully")
      setIsOpen(false)
    },
    // Shows the server's reason, e.g. a delete that would orphan an `else`.
    onError: (err: ApiError) => handleError(err),
    onSettled: () => {
      queryClient.invalidateQueries()
    },
  })

  const onSubmit = async () => {
    mutation.mutate(rulesetscript.id)
  }

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      role="alertdialog"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        {buttonElement || (
          <Button variant="ghost" size="sm" colorPalette="red">
            <FiTrash2 fontSize="16px" />
            Delete RulesetScript
          </Button>
        )}
      </DialogTrigger>

      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogCloseTrigger />
          <DialogHeader>
            <DialogTitle>Delete RulesetScript</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Badge colorPalette="red" variant="solid" mb={2}>
              {rulesetscript.key}=={rulesetscript.value}
            </Badge>
            <Text mb={4}>
              This item will be permanently deleted. Are you sure? You will not
              be able to undo this action.
            </Text>
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
              Delete
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </DialogRoot>
  )
}

export default DeleteRulesetScript
