import {
  Button,
  createListCollection,
  DialogActionTrigger,
  DialogTitle,
  Input,
  Select,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaPlus } from "react-icons/fa"

import {
  type ProfileScriptCreate,
  ProfilescriptsService,
  ProfilesService,
  TacacsServicesService,
} from "@/client"
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

const conditionCollection = createListCollection({
  items: [
    { label: "if", value: "if" },
    { label: "elif", value: "elif" },
    { label: "else", value: "else" },
  ],
})

const scriptActionCollection = createListCollection({
  items: [
    { label: "permit", value: "permit" },
    { label: "deny", value: "deny" },
  ],
})

interface AddProfileScriptProps {
  profileId?: string
  buttonElement?: React.ReactElement
}

const AddProfileScript = ({
  profileId,
  buttonElement,
}: AddProfileScriptProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isValid, isSubmitting },
  } = useForm<ProfileScriptCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      profile_id: profileId || "",
      condition: "if",
      action: "permit",
      key: "service",
      value: "",
      description: "",
    },
  })

  const watchedKey = watch("key")

  function getTacacsProfilesQueryOptions() {
    return {
      queryFn: () => ProfilesService.readProfiles(),
      queryKey: ["profiles"],
    }
  }
  const { data: data_profiles } = useQuery({
    ...getTacacsProfilesQueryOptions(),
    enabled: !profileId, // No need to query if parent ID is fixed
  })

  function getTacacsServicesQueryOptions() {
    return {
      queryFn: () => TacacsServicesService.readTacacsServices(),
      queryKey: ["tacacs_services"],
    }
  }
  const { data: data_services } = useQuery({
    ...getTacacsServicesQueryOptions(),
  })

  const items_tacacs_profiles = createListCollection<{
    value: string
    label: string
  }>({ items: [] })
  if (data_profiles && data_profiles.data.length > 0) {
    data_profiles.data.forEach((profile) => {
      items_tacacs_profiles.items.push({
        value: profile.id,
        label: profile.name,
      })
    })
  }

  const items_tacacs_services = createListCollection<{
    value: string
    label: string
  }>({ items: [] })
  if (data_services && data_services.data.length > 0) {
    data_services.data.forEach((service) => {
      items_tacacs_services.items.push({
        value: service.name,
        label: service.name,
      })
    })
  }

  const mutation = useMutation({
    mutationFn: (data: ProfileScriptCreate) =>
      ProfilescriptsService.createProfilescript({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("ProfileScript created successfully.")
      reset({
        profile_id: profileId || "",
        condition: "if",
        action: "permit",
        key: "service",
        value: "",
        description: "",
      })
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["profilescripts"] })
    },
  })

  const onSubmit: SubmitHandler<ProfileScriptCreate> = (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size={{ base: "md", md: "xl" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        {buttonElement || (
          <Button value="add-item" my={4}>
            <FaPlus fontSize="16px" />
            Add ProfileScript
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add ProfileScript</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Fill in the details to add a new item.</Text>
            <VStack gap={4}>
              {profileId ? (
                <input
                  type="hidden"
                  value={profileId}
                  {...register("profile_id", { required: true })}
                />
              ) : (
                <Field
                  required
                  invalid={!!errors.profile_id}
                  errorText={errors.profile_id?.message}
                  label="Profile Parent"
                >
                  <input
                    type="hidden"
                    {...register("profile_id", {
                      required: "Profile Parent is required.",
                    })}
                  />
                  <Select.Root
                    collection={items_tacacs_profiles}
                    size="sm"
                    onValueChange={(selection) => {
                      setValue("profile_id", selection.value.toString(), {
                        shouldValidate: true,
                      })
                    }}
                  >
                    <Select.Trigger>
                      <Select.ValueText placeholder="Select Tacacs Profile" />
                    </Select.Trigger>
                    <Select.Positioner>
                      <Select.Content>
                        <Select.ItemGroup>
                          {items_tacacs_profiles.items.map((item) => (
                            <Select.Item key={item.value} item={item.value}>
                              {item.label} - {item.value}
                              <Select.ItemIndicator />
                            </Select.Item>
                          ))}
                        </Select.ItemGroup>
                      </Select.Content>
                    </Select.Positioner>
                  </Select.Root>
                </Field>
              )}
              <Field
                required
                invalid={!!errors.condition}
                errorText={errors.condition?.message}
                label="Condition"
              >
                <input
                  type="hidden"
                  {...register("condition", {
                    required: "condition is required.",
                  })}
                />
                <Select.Root
                  collection={conditionCollection}
                  size="sm"
                  defaultValue={["if"]}
                  onValueChange={(selection) => {
                    setValue("condition", selection.value[0], {
                      shouldValidate: true,
                    })
                  }}
                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="Select Condition" />
                  </Select.Trigger>
                  <Select.Positioner>
                    <Select.Content>
                      <Select.ItemGroup>
                        {conditionCollection.items.map((item) => (
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
                required
                invalid={!!errors.key}
                errorText={errors.key?.message}
                label="Key"
              >
                <Input
                  {...register("key", {
                    required: "Key is required.",
                  })}
                  placeholder="Key"
                  type="text"
                />
              </Field>
              <Field
                required
                invalid={!!errors.value}
                errorText={errors.value?.message}
                label="value"
              >
                {watchedKey === "service" ? (
                  <>
                    <input
                      type="hidden"
                      {...register("value", { required: "value is required." })}
                    />
                    <Select.Root
                      collection={items_tacacs_services}
                      size="sm"
                      onValueChange={(selection) => {
                        setValue("value", selection.value.toString(), {
                          shouldValidate: true,
                        })
                      }}
                    >
                      <Select.Trigger>
                        <Select.ValueText placeholder="Select Tacacs Service" />
                      </Select.Trigger>
                      <Select.Positioner>
                        <Select.Content>
                          <Select.ItemGroup>
                            {items_tacacs_services.items.map((item) => (
                              <Select.Item key={item.value} item={item.value}>
                                {item.label}
                                <Select.ItemIndicator />
                              </Select.Item>
                            ))}
                          </Select.ItemGroup>
                        </Select.Content>
                      </Select.Positioner>
                    </Select.Root>
                  </>
                ) : (
                  <Input
                    {...register("value", { required: "value is required." })}
                    placeholder="value"
                    type="text"
                  />
                )}
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
                  collection={scriptActionCollection}
                  size="sm"
                  defaultValue={["permit"]}
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
                        {scriptActionCollection.items.map((item) => (
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
              Save
            </Button>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default AddProfileScript
