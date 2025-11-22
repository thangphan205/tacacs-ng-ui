import {
  Button,
  DialogActionTrigger,
  DialogTitle,
  Input,
  InputGroup,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaPlus } from "react-icons/fa"

import { type TacacsConfigCreate, TacacsConfigsService } from "@/client"
import type { ApiError } from "@/client/core/ApiError"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTrigger,
} from "../ui/dialog"
import { Field } from "../ui/field"

const AddTacacsConfig = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isValid, isSubmitting },
  } = useForm<TacacsConfigCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      filename: "",
      description: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: TacacsConfigCreate) =>
      TacacsConfigsService.createTacacsConfig({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("TacacsConfig created successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tacacs_configs"] })
    },
  })

  const onSubmit: SubmitHandler<TacacsConfigCreate> = (data) => {
    mutation.mutate(data)
  }

  useEffect(() => {
    if (isOpen) {
      const now = new Date()
      const year = now.getFullYear()
      const month = String(now.getMonth() + 1).padStart(2, "0")
      const day = String(now.getDate()).padStart(2, "0")
      const hours = String(now.getHours()).padStart(2, "0")
      const minutes = String(now.getMinutes()).padStart(2, "0")
      const seconds = String(now.getSeconds()).padStart(2, "0")
      const datetimeString = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
      const defaultFilename = `config_${year}-${month}-${day}_${hours}-${minutes}-${seconds}`

      reset({
        filename: defaultFilename,
        description: "generated at " + datetimeString,
      })
    }
  }, [isOpen, reset])

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button value="add-item" my={4}>
          <FaPlus fontSize="16px" />
          Add TacacsConfig
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add TacacsConfig</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Fill in the details to add a new item.</Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.filename}
                errorText={errors.filename?.message}
                label="filename"
              >
                <InputGroup endElement=".cfg">
                  <Input
                    {...register("filename", {
                      required: "Filename is required.",
                      maxLength: {
                        value: 30,
                        message: "Filename must be 30 characters or less.",
                      },
                      pattern: {
                        value: /^[a-zA-Z0-9._-]+$/,
                        message:
                          "Only alphanumerics, dots, underscores, and hyphens are allowed.",
                      },
                      validate: (value) =>
                        (value !== "." && value !== "..") ||
                        "Filename cannot be '.' or '..'",
                    })}
                    placeholder="filename"
                    type="text"
                  />
                </InputGroup>
              </Field>
              <Field
                invalid={!!errors.description}
                errorText={errors.description?.message}
                label="Description"
              >
                <Input
                  {...register("description")}
                  placeholder="Description"
                  type="text"
                />
              </Field>
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
              type="submit"
              disabled={!isValid}
              loading={isSubmitting}
            >
              Generate Tacacs Config
            </Button>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default AddTacacsConfig
