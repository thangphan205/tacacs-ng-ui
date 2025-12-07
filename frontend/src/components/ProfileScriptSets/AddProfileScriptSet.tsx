import {
  Button,
  createListCollection,
  DialogActionTrigger,
  DialogTitle,
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
import { FaPlus } from "react-icons/fa"

import { type ProfileScriptSetCreate, ProfilescriptsetsService, ProfilescriptsService } from "@/client"
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

const AddProfileScriptSet = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isValid, isSubmitting },
  } = useForm<ProfileScriptSetCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      key: "",
      description: "",
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
    mutationFn: (data: ProfileScriptSetCreate) =>
      ProfilescriptsetsService.createProfilescriptset({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("ProfileScriptSet created successfully.")
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

  const onSubmit: SubmitHandler<ProfileScriptSetCreate> = (data) => {
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
        <Button value="add-item" my={4}>
          <FaPlus fontSize="16px" />
          Add ProfileScriptSet
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add ProfileScriptSet</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Fill in the details to add a new item.</Text>
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
                    required: "key is required.",
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
                    required: "value is required.",
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
    </DialogRoot >
  )
}

export default AddProfileScriptSet
