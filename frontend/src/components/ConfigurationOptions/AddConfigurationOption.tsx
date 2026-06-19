import {
  Button,
  createListCollection,
  DialogActionTrigger,
  DialogTitle,
  Grid,
  GridItem,
  Input,
  Select,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import {
  FiCode,
  FiInfo,
  FiPlus,
  FiSliders,
  FiType,
} from "react-icons/fi"

import {
  type ConfigurationOptionCreate,
  ConfigurationOptionsService,
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
    icon: FiType,
    label: "Name / Scope",
    description:
      "The configuration scope this option applies to. Choose 'host', 'group', 'user', 'profile', or 'rule' to inject the config block into the corresponding section of the TACACS+ daemon config.",
    required: true,
  },
  {
    icon: FiCode,
    label: "Config Option",
    description:
      "The raw TACACS+ configuration text to inject. This is written verbatim into the daemon config file under the selected scope. Use tac_plus-ng syntax.",
    example: "enable = crypt \"$6$hash...\"",
    required: true,
  },
  {
    icon: FiInfo,
    label: "Description",
    description:
      "Optional notes explaining what this configuration option does. Not included in the generated config.",
  },
]

const AddConfigurationOption = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isValid, isSubmitting },
  } = useForm<ConfigurationOptionCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "",
      config_option: "",
      description: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: ConfigurationOptionCreate) =>
      ConfigurationOptionsService.createConfigurationOption({
        requestBody: data,
      }),
    onSuccess: () => {
      showSuccessToast("ConfigurationOption created successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["configuration_options"] })
    },
  })

  const onSubmit: SubmitHandler<ConfigurationOptionCreate> = (data) => {
    mutation.mutate(data)
  }

  const items_configuration_option = createListCollection<{
    value: string
    label: string
  }>({
    items: [
      { value: "host", label: "host" },
      { value: "group", label: "group" },
      { value: "user", label: "user" },
      { value: "profile", label: "profile" },
      { value: "rule", label: "rule" },
    ],
  })

  return (
    <DialogRoot
      size="xl"
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button value="add-item" my={4}>
          <FiPlus fontSize="16px" />
          Add ConfigurationOption
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add ConfigurationOption</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Add a raw configuration directive that will be injected into a
                  specific section of the generated TACACS+ config file.
                </Text>
                <VStack gap={4}>
                  <Field
                    required
                    invalid={!!errors.name}
                    errorText={errors.name?.message}
                    label="Name"
                  >
                    <Select.Root
                      collection={items_configuration_option}
                      onSelect={(selection) => {
                        setValue("name", selection.value)
                      }}
                      size="md"
                    >
                      <Select.Trigger>
                        <Select.ValueText placeholder="Select Configuration Option" />
                      </Select.Trigger>
                      <Select.Positioner>
                        <Select.Content>
                          {items_configuration_option.items.map((framework) => (
                            <Select.Item item={framework} key={framework.value}>
                              {framework.label}
                              <Select.ItemIndicator />
                            </Select.Item>
                          ))}
                        </Select.Content>
                      </Select.Positioner>
                    </Select.Root>
                  </Field>
                  <Field
                    required
                    invalid={!!errors.config_option}
                    errorText={errors.config_option?.message}
                    label="config_option"
                  >
                    <Textarea
                      {...register("config_option", {
                        required: "config_option is required.",
                      })}
                      rows={10}
                      placeholder="config_option"
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
              </GridItem>

              <GridItem>
                <FieldGuide
                  items={fieldGuideItems}
                  icon={FiSliders}
                  subtitle="Learn what each field means and how it maps to the TACACS+ daemon configuration."
                  howItWorks="Configuration options let you inject raw tac_plus-ng directives into specific sections of the generated config. The text is inserted verbatim, so ensure it follows valid tac_plus-ng syntax."
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

export default AddConfigurationOption
