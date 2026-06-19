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
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import { FiInfo, FiPlus, FiSettings, FiTool, FiType } from "react-icons/fi"

import { type TacacsServiceCreate, TacacsServicesService } from "@/client"
import type { ApiError } from "@/client/core/ApiError"
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

const AddTacacsService = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isValid, isSubmitting },
  } = useForm<TacacsServiceCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "",
      description: "",
      generate_config: true,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: TacacsServiceCreate) =>
      TacacsServicesService.createTacacsService({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("TacacsService created successfully.")
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

  const onSubmit: SubmitHandler<TacacsServiceCreate> = (data) => {
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
          Add TACACS Service
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add TACACS Service</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Create a new TACACS+ service definition. Services represent
                  authorization contexts (such as 'exec' for shell sessions or
                  'ppp' for network access) configured on network client
                  devices.
                </Text>
                <VStack gap={4}>
                  <Field
                    required
                    invalid={!!errors.name}
                    errorText={errors.name?.message}
                    label="Service Name"
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
                  howItWorks="Services define authorization contexts on network devices. When linked to a profile, they control which service attributes (e.g. privilege level, auto-command) are applied during authorization."
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

export default AddTacacsService
