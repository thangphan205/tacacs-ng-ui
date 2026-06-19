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
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"
import { FiInfo, FiSettings, FiTool, FiType } from "react-icons/fi"

import {
  type ApiError,
  type TacacsServicePublic,
  TacacsServicesService,
} from "@/client"
import FieldGuide, { type FieldGuideItem } from "@/components/Common/FieldGuide"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { Checkbox } from "../ui/checkbox"
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
    icon: FiType,
    label: "Service Name",
    description:
      "A unique identifier for the TACACS+ service. This maps to the authorization context configured on network devices (e.g. 'exec' for shell, 'ppp' for PPP sessions).",
    example: "exec, ppp, shell",
    required: true,
  },
  {
    icon: FiInfo,
    label: "Description",
    description:
      "Optional notes about what this service governs. Not included in the generated config — useful for documenting purpose.",
    example: "Shell access for interactive sessions",
  },
  {
    icon: FiSettings,
    label: "Generate to Config",
    description:
      "When enabled, this service will be included in the generated TACACS+ daemon configuration file. Disable to keep the record without activating it.",
  },
]

interface EditTacacsServiceProps {
  tacacs_service: TacacsServicePublic
}

interface TacacsServiceUpdateForm {
  name: string
  description?: string
  generate_config?: boolean
}

const EditTacacsService = ({ tacacs_service }: EditTacacsServiceProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<TacacsServiceUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...tacacs_service,
      description: tacacs_service.description ?? undefined,
      generate_config: tacacs_service.generate_config ?? true,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: TacacsServiceUpdateForm) =>
      TacacsServicesService.updateTacacsService({
        id: tacacs_service.id,
        requestBody: data,
      }),
    onSuccess: () => {
      showSuccessToast("TacacsService updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tacacs_services"] })
    },
  })

  const onSubmit: SubmitHandler<TacacsServiceUpdateForm> = async (data) => {
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
          Edit TACACS Service
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit TACACS Service</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Update the TACACS service details. Rules and scripts
                  referencing this service will inherit the updated parameters.
                </Text>
                <VStack gap={4}>
                  <Field
                    required
                    invalid={!!errors.name}
                    errorText={errors.name?.message}
                    label="Service Name"
                    helperText="A unique identifier for the service. Changing this will impact all rules and scripts referring to this service."
                  >
                    <Input
                      {...register("name", {
                        required: "Service Name is required.",
                      })}
                      placeholder="Service Name"
                      type="text"
                    />
                  </Field>
                  <Field
                    invalid={!!errors.description}
                    errorText={errors.description?.message}
                    label="Description"
                    helperText="Optional description or notes detailing what authorization attributes this service governs."
                  >
                    <Input
                      {...register("description")}
                      placeholder="Description"
                      type="text"
                    />
                  </Field>
                  <Controller
                    control={control}
                    name="generate_config"
                    render={({ field }) => (
                      <Field disabled={field.disabled} colorPalette="teal">
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={({ checked }) =>
                            field.onChange(checked)
                          }
                        >
                          Generate to TACACS+ Config
                        </Checkbox>
                      </Field>
                    )}
                  />
                </VStack>
              </GridItem>
              <GridItem>
                <FieldGuide
                  items={fieldGuideItems}
                  icon={FiTool}
                  subtitle="Learn what each field means and how it maps to the TACACS+ service configuration."
                  howItWorks="TACACS+ services represent authorization scopes (e.g. exec for shell, connection for specific interfaces) with associated key-value argument attributes."
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

export default EditTacacsService
