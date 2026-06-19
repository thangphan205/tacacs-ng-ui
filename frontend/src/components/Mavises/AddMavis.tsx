import {
  Button,
  DialogActionTrigger,
  DialogTitle,
  Grid,
  GridItem,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FiDatabase, FiKey, FiPlus, FiType } from "react-icons/fi"

import { type MavisCreate, MavisesService } from "@/client"
import type { ApiError } from "@/client/core/ApiError"
import FieldGuide, { type FieldGuideItem } from "@/components/Common/FieldGuide"
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

const fieldGuideItems: FieldGuideItem[] = [
  {
    icon: FiKey,
    label: "Mavis Key",
    description:
      "The configuration directive name for the MAVIS (LDAP/AD) backend. This maps directly to a key in the TACACS+ mavis module configuration block.",
    example: "host, base, scope, filter",
    required: true,
  },
  {
    icon: FiType,
    label: "Mavis Value",
    description:
      "The value for the configuration directive. This is the actual setting used by the MAVIS backend to connect to your directory service.",
    example: "ldap://dc01.example.com, dc=example,dc=com",
  },
]

const AddMavis = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isValid, isSubmitting },
  } = useForm<MavisCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      mavis_key: "",
      mavis_value: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: MavisCreate) =>
      MavisesService.createMavis({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Mavis created successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["mavises"] })
    },
  })

  const onSubmit: SubmitHandler<MavisCreate> = (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size="xl"
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button value="add-item" my={4}>
          <FiPlus fontSize="16px" />
          Add Mavis
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add Mavis</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Add a MAVIS (LDAP/AD backend) configuration setting. These
                  key-value pairs configure how the TACACS+ server connects to your
                  directory service for external authentication.
                </Text>
                <VStack gap={4}>
                  <Field
                    required
                    invalid={!!errors.mavis_key}
                    errorText={errors.mavis_key?.message}
                    label="Mavis Key"
                  >
                    <Input
                      {...register("mavis_key", {
                        required: "Key is required.",
                      })}
                      placeholder="Set Key"
                      type="text"
                    />
                  </Field>
                  <Field
                    invalid={!!errors.mavis_value}
                    errorText={errors.mavis_value?.message}
                    label="Mavis Value"
                  >
                    <Input
                      {...register("mavis_value")}
                      placeholder="Value"
                      type="text"
                    />
                  </Field>
                </VStack>
              </GridItem>

              <GridItem>
                <FieldGuide
                  items={fieldGuideItems}
                  icon={FiDatabase}
                  subtitle="Learn what each field means and how it maps to the MAVIS LDAP backend configuration."
                  howItWorks="MAVIS settings configure the external authentication backend. When a TACACS user has password type 'mavis', the server uses these settings to query your LDAP/AD directory for credential verification."
                />
              </GridItem>
            </Grid>
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
              Save
            </Button>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default AddMavis
