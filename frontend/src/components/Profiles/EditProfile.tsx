import {
  Button,
  ButtonGroup,
  createListCollection,
  DialogActionTrigger,
  Grid,
  GridItem,
  Input,
  Select,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"
import { FiInfo, FiSettings, FiShield, FiType } from "react-icons/fi"

import { type ApiError, type ProfilePublic, ProfilesService } from "@/client"
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
    label: "Name",
    description:
      "A unique name for the profile. Profiles group service-level attributes (e.g. privilege level, auto-commands) and are assigned to TACACS groups.",
    example: "admin_profile, readonly_exec",
    required: true,
  },
  {
    icon: FiShield,
    label: "Action",
    description:
      "The default authorization action: 'permit' allows access to the service, 'deny' blocks it. Individual script sets within the profile can override this.",
    required: true,
  },
  {
    icon: FiInfo,
    label: "Description",
    description:
      "Optional notes about the profile. Not included in the generated config — useful for documenting its purpose.",
  },
  {
    icon: FiSettings,
    label: "Generate to Config",
    description:
      "When enabled, this profile will be included in the generated TACACS+ daemon configuration file. Disable to keep the record without activating it.",
  },
]

interface EditProfileProps {
  profile: ProfilePublic
}

interface ProfileUpdateForm {
  name: string
  action: string
  description?: string
  generate_config?: boolean
}

const actionCollection = createListCollection({
  items: [
    { label: "permit", value: "permit" },
    { label: "deny", value: "deny" },
  ],
})

const EditProfile = ({ profile }: EditProfileProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors, isSubmitting },
  } = useForm<ProfileUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...profile,
      name: profile.name ?? undefined,
      action: profile.action ?? undefined,
      description: profile.description ?? undefined,
      generate_config: profile.generate_config ?? true,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: ProfileUpdateForm) =>
      ProfilesService.updateProfile({ id: profile.id, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Profile updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] })
    },
  })

  const onSubmit: SubmitHandler<ProfileUpdateForm> = async (data) => {
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
          Edit Profile
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit Profile</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Update the profile details. Changes will apply to all groups
                  referencing this profile.
                </Text>
                <VStack gap={4}>
                  <Field
                    required
                    invalid={!!errors.name}
                    errorText={errors.name?.message}
                    label="Name"
                  >
                    <Input
                      {...register("name", {
                        required: "Name is required",
                      })}
                      placeholder="name"
                      type="text"
                    />
                  </Field>
                  <Field
                    required
                    invalid={!!errors.action}
                    errorText={errors.action?.message}
                    label="Action"
                  >
                    <input
                      type="hidden"
                      {...register("action", {
                        required: "action is required",
                      })}
                    />
                    <Select.Root
                      collection={actionCollection}
                      size="sm"
                      defaultValue={[profile.action || "deny"]}
                      onValueChange={(selection) => {
                        setValue("action", selection.value[0], {
                          shouldValidate: true,
                        })
                      }}
                    >
                      <Select.Trigger>
                        <Select.ValueText placeholder="Select Action" />
                      </Select.Trigger>
                      <Select.Positioner>
                        <Select.Content>
                          <Select.ItemGroup>
                            {actionCollection.items.map((item) => (
                              <Select.Item key={item.value} item={item.value}>
                                {item.label}
                                <Select.ItemIndicator />
                              </Select.Item>
                            ))}
                          </Select.ItemGroup>
                        </Select.Content>
                      </Select.Positioner>
                    </Select.Root>
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
                  icon={FiShield}
                  subtitle="Learn what each field means and how it maps to the TACACS+ profile configuration."
                  howItWorks="A TACACS+ profile collects access rules and default authorization policies. Assigning a profile to a group sets the baseline commands/services that group members are allowed to execute."
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

export default EditProfile
