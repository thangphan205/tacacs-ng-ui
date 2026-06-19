import {
  Button,
  ButtonGroup,
  createListCollection,
  DialogActionTrigger,
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
import { FaExchangeAlt } from "react-icons/fa"
import { FiCode, FiInfo, FiKey, FiList, FiSliders } from "react-icons/fi"

import {
  type ApiError,
  ProfilesService,
  type RulesetScriptSetPublic,
  RulesetscriptsetsService,
  RulesetscriptsService,
} from "@/client"
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
  DialogTitle,
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

interface EditRulesetScriptSetProps {
  rulesetscriptset: RulesetScriptSetPublic
  buttonElement?: React.ReactElement
}

interface RulesetScriptSetUpdateForm {
  key: string
  value: string
  description?: string | null
  rulesetscript_id: string
}

const EditRulesetScriptSet = ({
  rulesetscriptset,
  buttonElement,
}: EditRulesetScriptSetProps) => {
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
      queryFn: () => RulesetscriptsService.readRulesetscripts(),
      queryKey: ["rulesetscripts"],
    }
  }

  const watchedKey = watch("key")

  const { data: data_rulesetscripts } = useQuery({
    ...getTacacsRulesetScriptsQueryOptions(),
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
    mutationFn: (data: RulesetScriptSetUpdateForm) =>
      RulesetscriptsetsService.updateRulesetscriptset({
        id: rulesetscriptset.id,
        requestBody: data,
      }),
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
      size="xl"
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => {
        setIsOpen(open)
        if (!open) {
          setFormKey((k) => k + 1)
          reset({
            key: rulesetscriptset.key,
            value: rulesetscriptset.value,
            description: rulesetscriptset.description ?? undefined,
            rulesetscript_id: rulesetscriptset.rulesetscript_id,
          })
        }
      }}
    >
      <DialogTrigger asChild>
        {buttonElement || (
          <Button variant="ghost">
            <FaExchangeAlt fontSize="16px" />
            Edit RulesetScriptSet
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <form key={formKey} onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit RulesetScriptSet</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Update the dynamic conditional ruleset script set variables.
                </Text>
                <VStack gap={4}>
                  <Field
                    required
                    invalid={!!errors.rulesetscript_id}
                    errorText={errors.rulesetscript_id?.message}
                    label="Ruleset Script Parent"
                  >
                    <input
                      type="hidden"
                      {...register("rulesetscript_id", {
                        required: "Ruleset Script Parent is required.",
                      })}
                    />
                    <Select.Root
                      collection={items_tacacs_rulesetscripts}
                      size="sm"
                      defaultValue={[rulesetscriptset.rulesetscript_id]}
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
                        <Select.ValueText placeholder="Select Tacacs RulesetScript" />
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
                          defaultValue={[rulesetscriptset.value]}
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
                                    <Select.ItemText>
                                      {item.label}
                                    </Select.ItemText>
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
                  subtitle="Learn what each field means and how it configures ruleset script parameters."
                  howItWorks="RulesetScriptSets allow you to define key-value variables that get dynamically set when their parent condition script succeeds. Commonly used to assign access profiles."
                />
              </GridItem>
            </Grid>
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
