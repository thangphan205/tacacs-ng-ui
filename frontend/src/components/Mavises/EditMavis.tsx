import {
  Button,
  ButtonGroup,
  DialogActionTrigger,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"

import { type ApiError, type MavisPublic, MavisesService } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog"
import { Field } from "../ui/field"

interface EditMavisProps {
  mavis: MavisPublic
}

interface MavisUpdateForm {
  mavis_key: string
  mavis_value: string
}

const EditMavis = ({ mavis }: EditMavisProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<MavisUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...mavis,
      mavis_key: mavis.mavis_key ?? undefined,
      mavis_value: mavis.mavis_value ?? undefined,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: MavisUpdateForm) =>
      MavisesService.updateMavis({ id: mavis.id, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Mavis updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["maviss"] })
    },
  })

  const onSubmit: SubmitHandler<MavisUpdateForm> = async (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost">
          <FaExchangeAlt fontSize="16px" />
          Edit Mavis
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit Mavis</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Update the item details below.</Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.mavis_key}
                errorText={errors.mavis_key?.message}
                label="Set Key"
              >
                <Input
                  {...register("mavis_key", {
                    required: "Key is required",
                  })}
                  placeholder="mavis_key"
                  type="text"
                />
              </Field>
              <Field
                invalid={!!errors.mavis_value}
                errorText={errors.mavis_value?.message}
                label="Value"
              >
                <Input
                  {...register("mavis_value")}
                  placeholder="Value"
                  type="text"
                />
              </Field>
            </VStack>
          </DialogBody>

          <DialogFooter gap={2}>
            <ButtonGroup>
              <DialogActionTrigger asChild>
                <Button
                  variant="subtle"
                  colorPalette="gray"
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
              </DialogActionTrigger>
              <Button variant="solid" type="submit" loading={isSubmitting}>
                Save
              </Button>
            </ButtonGroup>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default EditMavis
