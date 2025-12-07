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

import { type RulesetScriptSetCreate, RulesetscriptsetsService, RulesetscriptsService, ProfilesService } from "@/client"
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

const AddRulesetScriptSet = () => {
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
  } = useForm<RulesetScriptSetCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      key: "profile",
      description: "",
    },
  })

  const watchedKey = watch("key")

  function getTacacsRulesetScriptsQueryOptions() {
    return {
      queryFn: () =>
        RulesetscriptsService.readRulesetscripts(),
      queryKey: ["rulesetscripts",],
    }
  }
  const { data: data_rulesetscripts } = useQuery({
    ...getTacacsRulesetScriptsQueryOptions(),
  })

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

  let items_tacacs_rulesetscripts = createListCollection<{ value: string; label: string; description?: string }>({ items: [] });
  if (data_rulesetscripts && data_rulesetscripts.data.length > 0) {
    data_rulesetscripts.data.forEach((rulesetscript) => {
      items_tacacs_rulesetscripts.items.push({
        value: rulesetscript.id,
        label: "Ruleset: " + rulesetscript.ruleset_name,
        description: "RulesetScript: " + rulesetscript.condition + "(" + rulesetscript.key + "==" + rulesetscript.value + ")",
      });
    });
  }
  let items_tacacs_profiles = createListCollection<{ value: string; label: string; description?: string }>({ items: [] });
  if (data_profiles && data_profiles.data.length > 0) {
    data_profiles.data.forEach((profile) => {
      items_tacacs_profiles.items.push({
        value: profile.name,
        label: profile.name,
        description: profile.description || "",
      });
    });
  }

  const mutation = useMutation({
    mutationFn: (data: RulesetScriptSetCreate) =>
      RulesetscriptsetsService.createRulesetscriptset({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("RulesetScriptSet created successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["rulesetscriptsets"] })
    },
  })

  const onSubmit: SubmitHandler<RulesetScriptSetCreate> = (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size={{ base: "md", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button value="add-item" my={4}>
          <FaPlus fontSize="16px" />
          Add RulesetScriptSet
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add RulesetScriptSet</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Fill in the details to add a new item.</Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.rulesetscript_id}
                errorText={errors.rulesetscript_id?.message}
                label="Ruleset Script Parent"
              >
                <Select.Root
                  collection={items_tacacs_rulesetscripts}
                  size="sm"
                  onValueChange={(selection) => {
                    setValue("rulesetscript_id", selection.value.toString());
                  }}

                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="Select Tacacs ProfileScript" />
                  </Select.Trigger>
                  <Select.Positioner>
                    <Select.Content>
                      <Select.ItemGroup>
                        {items_tacacs_rulesetscripts.items.map((item) => (
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
                label="Key"
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
                label="Value"
              >
                {watchedKey === "profile" ? (
                  <Select.Root
                    collection={items_tacacs_profiles}
                    size="sm"
                    onValueChange={(selection) => {
                      setValue("value", selection.value.toString(), { shouldValidate: true });
                    }}
                  >
                    <Select.Trigger>
                      <Select.ValueText placeholder="Select a Profile" />
                    </Select.Trigger>
                    <Select.Positioner>
                      <Select.Content>
                        <Select.ItemGroup>
                          {items_tacacs_profiles.items.map((item) => (
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
                ) : (
                  <Input
                    {...register("value", {
                      required: "value is required.",
                    })}
                    placeholder="value"
                    type="text"
                  />
                )}
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

export default AddRulesetScriptSet
