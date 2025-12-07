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

import { type ApiError, type RulesetScriptSetPublic, RulesetscriptsetsService, RulesetscriptsService, ProfilesService } from "@/client"
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

interface EditRulesetScriptSetProps {
  rulesetscriptset: RulesetScriptSetPublic
}

interface RulesetScriptSetUpdateForm {
  key: string;
  value: string;
  description?: (string | null);
  rulesetscript_id: string;
}

const EditRulesetScriptSet = ({ rulesetscriptset }: EditRulesetScriptSetProps) => {
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
  } = useForm<RulesetScriptSetUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...rulesetscriptset,
      key: rulesetscriptset.key,
      value: rulesetscriptset.value,
      description: rulesetscriptset.description ?? undefined,
    },
  })
  function getTacacsRulesetScriptsQueryOptions() {
    return {
      queryFn: () =>
        RulesetscriptsService.readRulesetscripts(),
      queryKey: ["rulesetscripts",],
    }
  }

  const watchedKey = watch("key")

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
    mutationFn: (data: RulesetScriptSetUpdateForm) =>
      RulesetscriptsetsService.updateRulesetscriptset({ id: rulesetscriptset.id, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("RulesetScriptSet updated successfully.")
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

  const onSubmit: SubmitHandler<RulesetScriptSetUpdateForm> = async (data) => {
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
          Edit RulesetScriptSet
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit RulesetScriptSet</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Update the item details below.</Text>
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
                  defaultValue={[rulesetscriptset.rulesetscript_id]}
                  onValueChange={(selection) => {
                    setValue("rulesetscript_id", selection.value.toString());
                  }}

                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="Select Tacacs RulesetScript" />
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
                label="Value"
              >
                {watchedKey === "profile" ? (
                  <Select.Root
                    collection={items_tacacs_profiles}
                    size="sm"
                    defaultValue={[rulesetscriptset.value]}
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
                              <Select.ItemText>{item.label}</Select.ItemText>
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

export default EditRulesetScriptSet
