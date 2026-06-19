import {
  Button,
  createListCollection,
  DialogActionTrigger,
  DialogTitle,
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
import {
  FiInfo,
  FiPlus,
  FiSettings,
  FiShield,
  FiType,
} from "react-icons/fi"

import { type ProfileCreate, ProfilesService } from "@/client"
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

const actionCollection = createListCollection({
  items: [
    { label: "permit", value: "permit" },
    { label: "deny", value: "deny" },
  ],
})

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

const AddProfile = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors, isValid, isSubmitting },
  } = useForm<ProfileCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "",
      action: "deny",
      description: "",
      generate_config: true,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: ProfileCreate) =>
      ProfilesService.createProfile({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Profile created successfully.")
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

  const onSubmit: SubmitHandler<ProfileCreate> = (data) => {
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
          Add Profile
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add Profile</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Create a new authorization profile. Profiles define service-level
                  attributes and are linked to TACACS groups.
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
                        required: "Name is required.",
                      })}
                      placeholder="Name"
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
                        required: "action is required.",
                      })}
                    />
                    <Select.Root
                      collection={actionCollection}
                      size="sm"
                      defaultValue={["deny"]}
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
                          onCheckedChange={({ checked }) => field.onChange(checked)}
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
                  howItWorks="Profiles define authorization attributes for services. They contain script sets that specify attribute-value pairs (e.g. priv-lvl=15) applied when a user requests a service."
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

export default AddProfile
