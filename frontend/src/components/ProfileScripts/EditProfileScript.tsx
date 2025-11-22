import {
  Button,
  ButtonGroup,
  createListCollection,
  DialogActionTrigger,
  Input,
  Select,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"

import { type ApiError, type ProfileScriptPublic, ProfilescriptsService, ProfilesService, TacacsServicesService } from "@/client"
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

interface EditProfileScriptProps {
  profilescript: ProfileScriptPublic
}

interface ProfileScriptUpdateForm {
  condition: string;
  key: string;
  value: string;
  action: string;
  description?: (string | null);
  profile_id?: (string | null);
}

const EditProfileScript = ({ profilescript }: EditProfileScriptProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ProfileScriptUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...profilescript,
      profile_id: profilescript.profile_id ?? undefined,
      condition: profilescript.condition ?? undefined,
      description: profilescript.description ?? undefined,
      key: profilescript.key ?? undefined,
      value: profilescript.value ?? undefined,
      action: profilescript.action ?? undefined,
    },
  })

  const watchedKey = watch("key")

  function getTacacsProfilesQueryOptions() {
    return {
      queryFn: () =>
        ProfilesService.readProfiles(),
      queryKey: ["profiles",],
    }
  }
  const { data: data_profiles } = useQuery({
    ...getTacacsProfilesQueryOptions(),
  })
  function getTacacsServicesQueryOptions() {
    return {
      queryFn: () =>
        TacacsServicesService.readTacacsServices(),
      queryKey: ["tacacs_services",],
    }
  }
  const { data: data_services } = useQuery({
    ...getTacacsServicesQueryOptions(),
  })

  let items_tacacs_profiles = createListCollection<{ value: string; label: string }>({ items: [] });
  if (data_profiles && data_profiles.data.length > 0) {
    data_profiles.data.forEach((profile) => {
      items_tacacs_profiles.items.push({
        value: profile.id,
        label: profile.name,
      });
    });
  }
  let items_tacacs_services = createListCollection<{ value: string; label: string }>({ items: [] });
  if (data_services && data_services.data.length > 0) {
    data_services.data.forEach((service) => {
      items_tacacs_services.items.push({
        value: service.name,
        label: service.name,
      });
    });
  }
  const mutation = useMutation({
    mutationFn: (data: ProfileScriptUpdateForm) =>
      ProfilescriptsService.updateProfilescript({ id: profilescript.id, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("ProfileScript updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["profilescripts"] })
    },
  })

  const onSubmit: SubmitHandler<ProfileScriptUpdateForm> = async (data) => {
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
        <Button variant="ghost">
          <FaExchangeAlt fontSize="16px" />
          Edit ProfileScript
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit ProfileScript</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Update the item details below.</Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.profile_id}
                errorText={errors.profile_id?.message}
                label="Profile Parent"
              >
                <Select.Root
                  collection={items_tacacs_profiles}
                  size="sm"
                  defaultValue={[profilescript.profile_id || ""]}
                  onValueChange={(selection) => {
                    setValue("profile_id", selection.value.toString());
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
              <Field
                required
                invalid={!!errors.condition}
                errorText={errors.condition?.message}
                label="condition"
              >
                <Input
                  {...register("condition", {
                    required: "condition is required.",
                  })}
                  placeholder="condition"
                  type="text"
                />
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
                  <Select.Root
                    collection={items_tacacs_services}
                    size="sm"
                    defaultValue={[profilescript.value || ""]}
                    onValueChange={(selection) => {
                      setValue("value", selection.value.toString(), { shouldValidate: true });
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
                label="action"
              >
                <Input
                  {...register("action", {
                    required: "action is required.",
                  })}
                  placeholder="action"
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
            </VStack>
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
    </DialogRoot >
  )
}

export default EditProfileScript
