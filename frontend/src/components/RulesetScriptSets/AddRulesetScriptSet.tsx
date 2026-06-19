import {
  Button,
  createListCollection,
  DialogActionTrigger,
  DialogTitle,
  Grid,
  GridItem,
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
import {
  FiCode,
  FiInfo,
  FiKey,
  FiList,
  FiPlus,
  FiSliders,
} from "react-icons/fi"
import {
  ProfilesService,
  type RulesetScriptSetCreate,
  RulesetscriptsetsService,
  RulesetscriptsService,
} from "@/client"
import type { ApiError } from "@/client/core/ApiError"
import FieldGuide, { type FieldGuideItem } from "@/components/Common/FieldGuide"
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

const fieldGuideItems: FieldGuideItem[] = [
  {
    icon: FiSliders,
    label: "Ruleset Script Parent",
    description:
      "The conditional script block (e.g. 'if group == admin') inside which this variable is set.",
    required: true,
  },
  {
    icon: FiKey,
    label: "Key",
    description:
      "The variable key to configure (e.g. 'profile' to assign an authorization profile).",
    example: "profile, priv-lvl",
    required: true,
  },
  {
    icon: FiCode,
    label: "Value",
    description:
      "The value to set. If Key is 'profile', you can select an authorization profile; otherwise, enter a custom string.",
    example: "read_only_profile, admin_profile",
    required: true,
  },
  {
    icon: FiInfo,
    label: "Description",
    description:
      "Optional notes explaining what this variable configuration achieves.",
  },
]

interface AddRulesetScriptSetProps {
  rulesetscriptId?: string
  buttonElement?: React.ReactElement
}

const AddRulesetScriptSet = ({
  rulesetscriptId,
  buttonElement,
}: AddRulesetScriptSetProps) => {
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
      rulesetscript_id: rulesetscriptId || "",
      key: "profile",
      description: "",
    },
  })

  const watchedKey = watch("key")

  function getTacacsRulesetScriptsQueryOptions() {
    return {
      queryFn: () => RulesetscriptsService.readRulesetscripts(),
      queryKey: ["rulesetscripts"],
    }
  }
  const { data: data_rulesetscripts } = useQuery({
    ...getTacacsRulesetScriptsQueryOptions(),
    enabled: !rulesetscriptId,
  })

  function getTacacsProfilesQueryOptions() {
    return {
      queryFn: () => ProfilesService.readProfiles(),
      queryKey: ["profiles"],
    }
  }
  const { data: data_profiles } = useQuery({
    ...getTacacsProfilesQueryOptions(),
  })

  const items_tacacs_rulesetscripts = createListCollection<{
    value: string
    label: string
    description?: string
  }>({ items: [] })
  if (data_rulesetscripts && data_rulesetscripts.data.length > 0) {
    data_rulesetscripts.data.forEach((rulesetscript) => {
      items_tacacs_rulesetscripts.items.push({
        value: rulesetscript.id,
        label: `${rulesetscript.ruleset_name}: ${rulesetscript.condition}(${rulesetscript.key}==${rulesetscript.value})`,
        description: `Ruleset: ${rulesetscript.ruleset_name}`,
      })
    })
  }
  const items_tacacs_profiles = createListCollection<{
    value: string
    label: string
    description?: string
  }>({ items: [] })
  if (data_profiles && data_profiles.data.length > 0) {
    data_profiles.data.forEach((profile) => {
      items_tacacs_profiles.items.push({
        value: profile.name,
        label: profile.name,
        description: profile.description || "",
      })
    })
  }

  const mutation = useMutation({
    mutationFn: (data: RulesetScriptSetCreate) =>
      RulesetscriptsetsService.createRulesetscriptset({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("RulesetScriptSet created successfully.")
      reset({
        rulesetscript_id: rulesetscriptId || "",
        key: "profile",
        description: "",
      })
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
      size="xl"
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        {buttonElement || (
          <Button value="add-item" my={4}>
            <FiPlus fontSize="16px" />
            Add RulesetScriptSet
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add RulesetScriptSet</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Fill in the details to add a new command authorization script
                  variable assignment.
                </Text>
                <VStack gap={4}>
                  {rulesetscriptId ? (
                    <input
                      type="hidden"
                      value={rulesetscriptId}
                      {...register("rulesetscript_id", { required: true })}
                    />
                  ) : (
                    <Field
                      required
                      invalid={!!errors.rulesetscript_id}
                      errorText={errors.rulesetscript_id?.message}
                      label="Ruleset Script Parent"
                    >
                      <input
                        type="hidden"
                        {...register("rulesetscript_id", {
                          required: "rulesetscript_id is required.",
                        })}
                      />
                      <Select.Root
                        collection={items_tacacs_rulesetscripts}
                        size="sm"
                        onValueChange={(selection) => {
                          setValue(
                            "rulesetscript_id",
                            selection.value.toString(),
                            {
                              shouldValidate: true,
                            },
                          )
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
                                    <Select.ItemText>
                                      {item.label}
                                    </Select.ItemText>
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
                  )}
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
                      <>
                        <input
                          type="hidden"
                          {...register("value", {
                            required: "value is required.",
                          })}
                        />
                        <Select.Root
                          collection={items_tacacs_profiles}
                          size="sm"
                          onValueChange={(selection) => {
                            setValue("value", selection.value.toString(), {
                              shouldValidate: true,
                            })
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
                                      <Select.ItemText>
                                        {item.label}
                                      </Select.ItemText>
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
                      </>
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
              </GridItem>

              <GridItem>
                <FieldGuide
                  items={fieldGuideItems}
                  icon={FiList}
                  subtitle="Learn what each field means and how it maps to the command authorization script variable settings."
                  howItWorks="When a script block matches, the settings specified inside are applied (such as linking a specific authorization Profile)."
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

export default AddRulesetScriptSet
