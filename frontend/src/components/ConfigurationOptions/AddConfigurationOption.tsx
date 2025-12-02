import {
  Button,
  createListCollection,
  DialogActionTrigger,
  DialogTitle,
  Input,
  Select,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaPlus } from "react-icons/fa"

import { type ConfigurationOptionCreate, ConfigurationOptionsService } from "@/client"
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
      ConfigurationOptionsService.createConfigurationOption({ requestBody: data }),
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

  const items_configuration_option = createListCollection<{ value: string; label: string }>({
    items: [
      { value: 'host', label: 'host' },
      { value: 'group', label: 'group' },
      { value: 'user', label: 'user' },
      { value: 'profile', label: 'profile' },
      { value: 'rule', label: 'rule' },
    ],
  });

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
          Add ConfigurationOption
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add ConfigurationOption</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Fill in the details to add a new item.</Text>
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
                    setValue("name", selection.value);
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
