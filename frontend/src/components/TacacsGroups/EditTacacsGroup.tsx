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
import { FiInfo, FiSettings, FiType, FiUsers } from "react-icons/fi"
import {
  type ApiError,
  type TacacsGroupPublic,
  TacacsGroupsService,
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
    label: "Group Name",
    description:
      "A unique identifier for the TACACS group. Users assigned to this group inherit its profiles, services, and command authorization rules.",
    example: "admin, noc_operators, read_only",
    required: true,
  },
  {
    icon: FiInfo,
    label: "Description",
    description:
      "Optional notes describing the group's purpose or permission level. Not included in the generated config.",
    example: "Full admin access for senior engineers",
  },
  {
    icon: FiSettings,
    label: "Generate to Config",
    description:
      "When enabled, this group will be included in the generated TACACS+ daemon configuration file. Disable to keep the record without activating it.",
  },
]

interface EditTacacsGroupProps {
  tacacs_group: TacacsGroupPublic
}

interface TacacsGroupUpdateForm {
  group_name: string
  description?: string
  generate_config?: boolean
}

const EditTacacsGroup = ({ tacacs_group }: EditTacacsGroupProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<TacacsGroupUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...tacacs_group,
      description: tacacs_group.description ?? undefined,
      generate_config: tacacs_group.generate_config ?? true,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: TacacsGroupUpdateForm) =>
      TacacsGroupsService.updateTacacsGroup({
        id: tacacs_group.id,
        requestBody: data,
      }),
    onSuccess: () => {
      showSuccessToast("TacacsGroup updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tacacs_groups"] })
    },
  })

  const onSubmit: SubmitHandler<TacacsGroupUpdateForm> = async (data) => {
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
          Edit TACACS Group
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit TACACS Group</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Update the TACACS group details. Users assigned to this group
                  will inherit these modified parameters.
                </Text>
                <VStack gap={4}>
                  <Field
                    required
                    invalid={!!errors.group_name}
                    errorText={errors.group_name?.message}
                    label="Group Name"
                    helperText="A unique identifier for the TACACS group. Changing this will affect all users who are members of this group."
                  >
                    <Input
                      {...register("group_name", {
                        required: "Group Name is required.",
                      })}
                      placeholder="Group Name"
                      type="text"
                    />
                  </Field>

                  <Field
                    invalid={!!errors.description}
                    errorText={errors.description?.message}
                    label="Description"
                    helperText="Optional description or notes detailing the group's purpose or permission level."
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
                  icon={FiUsers}
                  subtitle="Learn what each field means and how it maps to the TACACS+ group configuration."
                  howItWorks='When "Generate to Config" is enabled, this group is written as a group block in the TACACS+ daemon config. Users referencing this group will inherit its authorization settings.'
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

export default EditTacacsGroup
