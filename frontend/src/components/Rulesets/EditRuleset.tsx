import {
  Button,
  ButtonGroup,
  createListCollection,
  DialogActionTrigger,
  Grid,
  GridItem,
  Input,
  Select,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"
import { FiInfo, FiSettings, FiShield, FiType } from "react-icons/fi"

import { type ApiError, type RulesetPublic, RulesetsService } from "@/client"
import FieldGuide, { type FieldGuideItem } from "@/components/Common/FieldGuide"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { Checkbox } from "../ui/checkbox"
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
    icon: FiType,
    label: "Name",
    description:
      "A unique name for the ruleset. Rulesets group command authorization rules (e.g. which CLI commands a user can execute) and are assigned to TACACS groups.",
    example: "show_only, full_config_access",
    required: true,
  },
  {
    icon: FiShield,
    label: "Action",
    description:
      "The default command authorization action: 'permit' allows command execution, 'deny' blocks it. Individual script sets within the ruleset can override this.",
    required: true,
  },
  {
    icon: FiInfo,
    label: "Description",
    description:
      "Optional notes about the ruleset. Not included in the generated config — useful for documenting its purpose.",
  },
  {
    icon: FiSettings,
    label: "Generate to Config",
    description:
      "When enabled, this ruleset will be included in the generated TACACS+ daemon configuration file. Disable to keep the record without activating it.",
  },
]

interface EditRulesetProps {
  ruleset: RulesetPublic
}

interface RulesetUpdateForm {
  name: string
  action: string
  description?: string
  generate_config?: boolean
}

const actionCollection = createListCollection({
  items: [
    { label: "permit", value: "permit" },
    { label: "deny", value: "deny" },
  ],
})

const EditRuleset = ({ ruleset }: EditRulesetProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors, isSubmitting },
  } = useForm<RulesetUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...ruleset,
      name: ruleset.name ?? undefined,
      action: ruleset.action ?? undefined,
      description: ruleset.description ?? undefined,
      generate_config: ruleset.generate_config ?? true,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: RulesetUpdateForm) =>
      RulesetsService.updateRuleset({ id: ruleset.id, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Ruleset updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["rulesets"] })
    },
  })

  const onSubmit: SubmitHandler<RulesetUpdateForm> = async (data) => {
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
        <Button variant="ghost">
          <FaExchangeAlt fontSize="16px" />
          Edit Ruleset
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit Ruleset</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Update the ruleset details. Changes will apply to all groups
                  referencing this ruleset.
                </Text>
                <VStack gap={4}>
                  <Field
                    required
                    invalid={!!errors.name}
                    errorText={errors.name?.message}
                    label="Name"
                  >
                    <Input
                      {...register("name", {
                        required: "Name is required",
                      })}
                      placeholder="name"
                      type="text"
                    />
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
                        required: "action is required",
                      })}
                    />
                    <Select.Root
                      collection={actionCollection}
                      size="sm"
                      defaultValue={[ruleset.action || "deny"]}
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
                            {actionCollection.items.map((item) => (
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
                  <Controller
                    control={control}
                    name="generate_config"
                    render={({ field }) => (
                      <Field disabled={field.disabled} colorPalette="teal">
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={({ checked }) =>
                            field.onChange(checked)
                          }
                        >
                          Generate to TACACS+ Config
                        </Checkbox>
                      </Field>
                    )}
                  />
                </VStack>
              </GridItem>
              <GridItem>
                <FieldGuide
                  items={fieldGuideItems}
                  icon={FiShield}
                  subtitle="Learn what each field means and how it maps to the TACACS+ ruleset configuration."
                  howItWorks="A TACACS+ ruleset controls command-level authorization. When a user runs a command on a network device, the daemon evaluates these rules in order to either permit or deny execution."
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

export default EditRuleset
