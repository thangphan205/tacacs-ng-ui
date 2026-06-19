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
  type ProfileScriptSetCreate,
  ProfilescriptsetsService,
  ProfilescriptsService,
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
    label: "ProfileScript Parent",
    description:
      "The conditional script block (e.g. 'if service == shell') inside which this variable is set.",
    required: true,
  },
  {
    icon: FiKey,
    label: "Set Key",
    description:
      "The parameter or attribute name to configure (e.g. 'priv-lvl' or service-specific parameters).",
    example: "priv-lvl, timeout, shell:priv-lvl",
    required: true,
  },
  {
    icon: FiCode,
    label: "Set Value",
    description:
      "The value to assign to the key. Can be a numeric level, a string, or configuration details.",
    example: "15, 60, true",
    required: true,
  },
  {
    icon: FiInfo,
    label: "Description",
    description:
      "Optional notes explaining what this variable configuration achieves.",
  },
]

interface AddProfileScriptSetProps {
  profilescriptId?: string
  buttonElement?: React.ReactElement
}

const AddProfileScriptSet = ({
  profilescriptId,
  buttonElement,
}: AddProfileScriptSetProps) => {
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
      profilescript_id: profilescriptId || "",
      key: "",
      value: "",
      description: "",
    },
  })

  function getTacacsProfileScriptsQueryOptions() {
    return {
      queryFn: () => ProfilescriptsService.readProfilescripts(),
      queryKey: ["profilescripts"],
    }
  }
  const { data: data_profilescripts } = useQuery({
    ...getTacacsProfileScriptsQueryOptions(),
    enabled: !profilescriptId, // Skip query if script ID is fixed
  })

  const items_tacacs_profilescripts = createListCollection<{
    value: string
    label: string
    description?: string
  }>({ items: [] })
  if (data_profilescripts && data_profilescripts.data.length > 0) {
    data_profilescripts.data.forEach((profilescript) => {
      items_tacacs_profilescripts.items.push({
        value: profilescript.id,
        label: `${profilescript.profile_name || "No Profile"}: ${profilescript.condition}(${profilescript.key}==${profilescript.value})`,
        description: `Profile: ${profilescript.profile_name || "No Profile"}`,
      })
    })
  }

  const mutation = useMutation({
    mutationFn: (data: ProfileScriptSetCreate) =>
      ProfilescriptsetsService.createProfilescriptset({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("ProfileScriptSet created successfully.")
      reset({
        profilescript_id: profilescriptId || "",
        key: "",
        value: "",
        description: "",
      })
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
      size="xl"
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        {buttonElement || (
          <Button value="add-item" my={4}>
            <FiPlus fontSize="16px" />
            Add ProfileScriptSet
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add ProfileScriptSet</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Fill in the details to add a new dynamic profile script
                  variable assignment.
                </Text>
                <VStack gap={4}>
                  {profilescriptId ? (
                    <input
                      type="hidden"
                      value={profilescriptId}
                      {...register("profilescript_id", { required: true })}
                    />
                  ) : (
                    <Field
                      required
                      invalid={!!errors.profilescript_id}
                      errorText={errors.profilescript_id?.message}
                      label="ProfileScript Parent"
                    >
                      <input
                        type="hidden"
                        {...register("profilescript_id", {
                          required: "profilescript_id is required.",
                        })}
                      />
                      <Select.Root
                        collection={items_tacacs_profilescripts}
                        size="sm"
                        onValueChange={(selection) => {
                          setValue(
                            "profilescript_id",
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
                              {items_tacacs_profilescripts.items.map((item) => (
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
              </GridItem>

              <GridItem>
                <FieldGuide
                  items={fieldGuideItems}
                  icon={FiList}
                  subtitle="Learn what each field means and how it maps to the dynamic variable assignments."
                  howItWorks="Variable assignments configure parameters like privilege level or session timeout inside the matching conditional blocks."
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

export default AddProfileScriptSet
