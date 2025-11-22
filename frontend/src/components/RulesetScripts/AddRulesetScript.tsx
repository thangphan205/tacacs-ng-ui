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

import { type RulesetScriptCreate, RulesetscriptsService, RulesetsService, TacacsGroupsService } from "@/client"
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

const AddRulesetScript = () => {
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
  } = useForm<RulesetScriptCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      condition: "if",
      key: "group",
      value: "",
      description: "",
      action: "permit"
    },
  })

  const keyField = watch("key")

  function getTacacsProfilesQueryOptions() {
    return {
      queryFn: () =>
        RulesetsService.readRulesets(),
      queryKey: ["rulesets",],
    }
  }
  const { data: data_rulesets } = useQuery({
    ...getTacacsProfilesQueryOptions(),
  })

  function getTacacsGroupsQueryOptions() {
    return {
      queryFn: () =>
        TacacsGroupsService.readTacacsGroups(),
      queryKey: ["tacacs_groups",],
    }
  }
  const { data: data_groups } = useQuery({
    ...getTacacsGroupsQueryOptions(),
  })


  let items_tacacs_rulesets = createListCollection<{ value: string; label: string }>({ items: [] });
  if (data_rulesets && data_rulesets.data.length > 0) {
    data_rulesets.data.forEach((ruleset) => {
      items_tacacs_rulesets.items.push({
        value: ruleset.id,
        label: ruleset.name,
      });
    });
  }

  let items_tacacs_groups = createListCollection<{ value: string; label: string }>({ items: [] });
  if (data_groups && data_groups.data.length > 0) {
    data_groups.data.forEach((group) => {
      items_tacacs_groups.items.push({
        value: group.group_name,
        label: group.group_name,
      });
    });
  }
  const mutation = useMutation({
    mutationFn: (data: RulesetScriptCreate) =>
      RulesetscriptsService.createRulesetscript({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("RulesetScript created successfully.")
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

  const onSubmit: SubmitHandler<RulesetScriptCreate> = (data) => {
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
          Add RulesetScript
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add RulesetScript</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Fill in the details to add a new item.</Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.ruleset_id}
                errorText={errors.ruleset_id?.message}
                label="Ruleset Parent"
              >
                <Select.Root
                  collection={items_tacacs_rulesets}
                  size="sm"
                  onValueChange={(selection) => {
                    setValue("ruleset_id", selection.value.toString());
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
                {keyField === "group" ? (
                  <Select.Root
                    collection={items_tacacs_groups}
                    size="sm"
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

export default AddRulesetScript
