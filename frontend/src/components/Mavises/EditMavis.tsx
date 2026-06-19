import {
  Button,
  ButtonGroup,
  DialogActionTrigger,
  Grid,
  GridItem,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"
import { FiDatabase, FiKey, FiType } from "react-icons/fi"

import { type ApiError, MavisesService, type MavisPublic } from "@/client"
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
  DialogTitle,
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
      queryClient.invalidateQueries({ queryKey: ["mavises"] })
    },
  })

  const onSubmit: SubmitHandler<MavisUpdateForm> = async (data) => {
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
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Update the MAVIS configuration details. These key-value
                  settings configure LDAP/AD server connectivity parameters.
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
                        required: "Key is required",
                      })}
                      placeholder="mavis_key"
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
                  subtitle="Learn what each field means and how it maps to the MAVIS LDAP module config."
                  howItWorks="The MAVIS backend acts as an external authenticator, allowing the TACACS+ daemon to query LDAP or Active Directory to verify user credentials."
                />
              </GridItem>
            </Grid>
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
