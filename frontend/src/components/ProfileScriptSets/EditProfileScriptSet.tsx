import {
  Button,
  ButtonGroup,
  createListCollection,
  DialogActionTrigger,
  Input,
  Select,
  Span,
  Stack,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"

import { type ApiError, type ProfileScriptSetPublic, ProfilescriptsetsService, ProfilescriptsService } from "@/client"
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

interface EditProfileScriptSetProps {
  profilescriptset: ProfileScriptSetPublic
}

interface ProfileScriptSetUpdateForm {
  key: string;
  value: string;
  description?: (string | null);
  profilescript_id: string;
}

const EditProfileScriptSet = ({ profilescriptset }: EditProfileScriptSetProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<ProfileScriptSetUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...profilescriptset,
      description: profilescriptset.description ?? undefined,
    },
  })
  function getTacacsProfileScriptsQueryOptions() {
    return {
      queryFn: () =>
        ProfilescriptsService.readProfilescripts(),
      queryKey: ["profilescripts",],
    }
  }
  const { data: data_profilescripts } = useQuery({
    ...getTacacsProfileScriptsQueryOptions(),
  })


  let items_tacacs_profilescripts = createListCollection<{ value: string; label: string; description?: string }>({ items: [] });
  if (data_profilescripts && data_profilescripts.data.length > 0) {
    data_profilescripts.data.forEach((profilescript) => {
      items_tacacs_profilescripts.items.push({
        value: profilescript.id,
        label: "Profile: " + profilescript.profile_name || "No Profile",
        description: "ProfileScript: " + profilescript.condition + "(" + profilescript.key + "==" + profilescript.value + ")",
      });
    });
  }



  const mutation = useMutation({
    mutationFn: (data: ProfileScriptSetUpdateForm) =>
      ProfilescriptsetsService.updateProfilescriptset({ id: profilescriptset.id, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("ProfileScriptSet updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["profilescriptsets"] })
    },
  })

  const onSubmit: SubmitHandler<ProfileScriptSetUpdateForm> = async (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost">
          <FaExchangeAlt fontSize="16px" />
          Edit ProfileScriptSet
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit ProfileScriptSet</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Update the item details below.</Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.profilescript_id}
                errorText={errors.profilescript_id?.message}
                label="ProfileScript Parent"
              >
                <Select.Root
                  collection={items_tacacs_profilescripts}
                  size="sm"
                  defaultValue={[profilescriptset.profilescript_id]}
                  onValueChange={(selection) => {
                    setValue("profilescript_id", selection.value.toString());
                  }}

                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="Select Tacacs ProfileScript" />
                  </Select.Trigger>
                  <Select.Positioner>
                    <Select.Content>
                      <Select.ItemGroup>
                        {items_tacacs_profilescripts.items.map((item) => (
                          <Select.Item item={item} key={item.value}>
                            <Stack gap="0">
                              <Select.ItemText>{item.label}</Select.ItemText>
                              <Span color="fg.muted" textStyle="xs">
                                {item.description}
                              </Span>
                            </Stack>
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
                label="Set Key"
              >
                <Input
                  {...register("key", {
                    required: "key is required",
                  })}
                  placeholder="key"
                  type="text"
                />
              </Field>
              <Field
                required
                invalid={!!errors.value}
                errorText={errors.value?.message}
                label="Set Value"
              >
                <Input
                  {...register("value", {
                    required: "value is required",
                  })}
                  placeholder="value"
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
    </DialogRoot>
  )
}

export default EditProfileScriptSet
