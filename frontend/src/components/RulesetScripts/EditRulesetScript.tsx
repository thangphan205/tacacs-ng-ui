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

import {
  type ApiError,
  type RulesetScriptPublic,
  RulesetscriptsService,
  RulesetsService,
  TacacsGroupsService,
} from "@/client"
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

interface EditRulesetScriptProps {
  rulesetscript: RulesetScriptPublic
  buttonElement?: React.ReactElement
}

interface RulesetScriptUpdateForm {
  condition: string
  key: string
  value: string
  action: string
  description?: string | null
  ruleset_id: string
}

const EditRulesetScript = ({
  rulesetscript,
  buttonElement,
}: EditRulesetScriptProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [formKey, setFormKey] = useState(0)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RulesetScriptUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...rulesetscript,
      description: rulesetscript.description ?? undefined,
      key: rulesetscript.key ?? undefined,
      value: rulesetscript.value ?? undefined,
      action: rulesetscript.action ?? undefined,
      ruleset_id: rulesetscript.ruleset_id ?? undefined,
      condition: rulesetscript.condition ?? undefined,
    },
  })
  const keyField = watch("key")

  function getTacacsProfilesQueryOptions() {
    return {
      queryFn: () => RulesetsService.readRulesets(),
      queryKey: ["rulesets"],
    }
  }
  const { data: data_rulesets } = useQuery({
    ...getTacacsProfilesQueryOptions(),
  })

  function getTacacsGroupsQueryOptions() {
    return {
      queryFn: () => TacacsGroupsService.readTacacsGroups(),
      queryKey: ["tacacs_groups"],
    }
  }
  const { data: data_groups } = useQuery({
    ...getTacacsGroupsQueryOptions(),
  })

  const items_tacacs_rulesets = createListCollection<{
    value: string
    label: string
  }>({ items: [] })
  if (data_rulesets && data_rulesets.data.length > 0) {
    data_rulesets.data.forEach((ruleset) => {
      items_tacacs_rulesets.items.push({
        value: ruleset.id,
        label: ruleset.name,
      })
    })
  }

  const items_tacacs_groups = createListCollection<{
    value: string
    label: string
  }>({ items: [] })
  if (data_groups && data_groups.data.length > 0) {
    data_groups.data.forEach((group) => {
      items_tacacs_groups.items.push({
        value: group.group_name,
        label: group.group_name,
      })
    })
  }

  const mutation = useMutation({
    mutationFn: (data: RulesetScriptUpdateForm) =>
      RulesetscriptsService.updateRulesetscript({
        id: rulesetscript.id,
        requestBody: data,
      }),
    onSuccess: () => {
      showSuccessToast("RulesetScript updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["rulesetscripts"] })
    },
  })

  const onSubmit: SubmitHandler<RulesetScriptUpdateForm> = async (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size={{ base: "md", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => {
        setIsOpen(open)
        if (!open) {
          setFormKey((k) => k + 1)
          reset({
            condition: rulesetscript.condition ?? undefined,
            key: rulesetscript.key ?? undefined,
            value: rulesetscript.value ?? undefined,
            action: rulesetscript.action ?? undefined,
            description: rulesetscript.description ?? undefined,
            ruleset_id: rulesetscript.ruleset_id ?? undefined,
          })
        }
      }}
    >
      <DialogTrigger asChild>
        {buttonElement || (
          <Button variant="ghost">
            <FaExchangeAlt fontSize="16px" />
            Edit RulesetScript
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <form key={formKey} onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit RulesetScript</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Update the item details below.</Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.ruleset_id}
                errorText={errors.ruleset_id?.message}
                label="Ruleset Parent"
              >
                <input
                  type="hidden"
                  {...register("ruleset_id", {
                    required: "Ruleset Parent is required.",
                  })}
                />
                <Select.Root
                  collection={items_tacacs_rulesets}
                  size="sm"
                  defaultValue={[rulesetscript.ruleset_id]}
                  onValueChange={(selection) => {
                    setValue("ruleset_id", selection.value.toString(), {
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
                        {items_tacacs_rulesets.items.map((item) => (
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
                  defaultValue={[rulesetscript.condition || "if"]}
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
                {keyField === "group" ? (
                  <>
                    <input
                      type="hidden"
                      {...register("value", { required: "value is required." })}
                    />
                    <Select.Root
                      collection={items_tacacs_groups}
                      size="sm"
                      defaultValue={[rulesetscript.value]}
                      onValueChange={(selection) => {
                        setValue("value", selection.value.toString(), {
                          shouldValidate: true,
                        })
                      }}
                    >
                      <Select.Trigger>
                        <Select.ValueText placeholder="Select Tacacs Group" />
                      </Select.Trigger>
                      <Select.Positioner>
                        <Select.Content>
                          <Select.ItemGroup>
                            {items_tacacs_groups.items.map((item) => (
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
                  defaultValue={[rulesetscript.action || "permit"]}
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

export default EditRulesetScript
