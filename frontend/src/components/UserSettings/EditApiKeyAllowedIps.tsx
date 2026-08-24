import { Button, DialogTitle, Text, Textarea } from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FiEdit2 } from "react-icons/fi"

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
import { Field } from "../ui/field"

interface FormValues {
  allowed_ips: string
}

const EditApiKeyAllowedIps = ({ apiKey }: { apiKey: ApiKeyPublic }) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    defaultValues: {
      allowed_ips: apiKey.allowed_ips?.split(",").join("\n") ?? "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
      ApiKeysService.updateApiKeyAllowedIps({
        id: apiKey.id,
        requestBody: {
          allowed_ips:
            data.allowed_ips
              .split("\n")
              .map((s) => s.trim())
              .filter(Boolean)
              .join(",") || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Allowed source IPs updated.")
      setIsOpen(false)
    },
    onError: (err: ApiError) => handleError(err),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    },
  })

  const onSubmit: SubmitHandler<FormValues> = (data) => mutation.mutate(data)

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => {
        setIsOpen(open)
        if (!open) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button variant="ghost" size="xs">
          <FiEdit2 fontSize="14px" />
          Edit IPs
        </Button>
      </DialogTrigger>

      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <DialogCloseTrigger />
          <DialogHeader>
            <DialogTitle>Edit Allowed Source IPs</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4} fontSize="sm" color="gray.500">
              Only the source-IP restriction for “{apiKey.name}” can be changed
              after creation.
            </Text>
            <Field
              invalid={!!errors.allowed_ips}
              errorText={errors.allowed_ips?.message}
              label="Allowed source IPs"
              helperText="Optional. One IPv4/IPv6 address or CIDR per line. Leave blank to allow any source."
            >
              <Textarea
                {...register("allowed_ips")}
                placeholder={"203.0.113.4\n198.51.100.0/24\n2001:db8::/32"}
                rows={3}
              />
            </Field>
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
            <Button variant="solid" type="submit" loading={isSubmitting}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </DialogRoot>
  )
}

export default EditApiKeyAllowedIps
