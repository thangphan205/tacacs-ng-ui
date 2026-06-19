import {
  Alert,
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
import { useMemo, useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import { FaPlus } from "react-icons/fa"

import {
  TacacsGroupsService,
  type TacacsUserCreate,
  TacacsUsersService,
} from "@/client"
import type { ApiError } from "@/client/core/ApiError"
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
  DialogTrigger,
} from "../ui/dialog"
import { Field } from "../ui/field"

const AddTacacsUser = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [isSelectMavis, setIsSelectMavis] = useState(false)
  const [isSelectClear, setIsSelectClear] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors, isValid, isSubmitting },
  } = useForm<TacacsUserCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      username: "",
      description: "",
      member: "",
      password_type: "crypt",
      generate_config: true,
    },
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

  const items_tacacs_groups = useMemo(
    () =>
      createListCollection({
        items: (data_groups?.data ?? []).map((g) => ({
          value: g.group_name,
          label: g.group_name,
        })),
      }),
    [data_groups],
  )

  const items_password_type = createListCollection({
    items: [
      { value: "clear", label: "clear" },
      { value: "crypt", label: "crypt" },
      { value: "mavis", label: "mavis" },
    ],
  })

  const mutation = useMutation({
    mutationFn: (data: TacacsUserCreate) =>
      TacacsUsersService.createTacacsUser({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("TacacsUser created successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tacacs_users"] })
    },
  })

  const onSubmit: SubmitHandler<TacacsUserCreate> = (data) => {
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
        <Button value="add-item" my={4}>
          <FaPlus fontSize="16px" />
          Add TACACS User
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add TACACS User</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4} color="fg.muted" fontSize="sm">
              Create a new user account. Local logins support secure hashing
              (crypt) or plaintext (clear), while mavis delegates auth to remote
              servers (LDAP/AD).
            </Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.username}
                errorText={errors.username?.message}
                label="Username"
                helperText="The unique login username used to authenticate against the network client (NAS)."
              >
                <Input
                  {...register("username", {
                    required: "username is required.",
                  })}
                  placeholder="username"
                  type="text"
                />
              </Field>
              <Field
                required
                invalid={!!errors.password_type}
                errorText={errors.password_type?.message}
                label="Password Type"
                helperText="Recommended: Use 'crypt' to encrypt passwords securely on the server."
              >
                <input
                  type="hidden"
                  {...register("password_type", {
                    required: "Password type is required.",
                    value: "crypt",
                  })}
                />
                <Select.Root
                  collection={items_password_type}
                  defaultValue={["crypt"]}
                  onValueChange={(selection) => {
                    const val = selection.value[0] ?? ""
                    setValue("password_type", val, { shouldValidate: true })
                    setIsSelectMavis(val === "mavis")
                    setIsSelectClear(val === "clear")
                  }}
                  size="sm"
                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="Select password type" />
                  </Select.Trigger>
                  <Select.Positioner>
                    <Select.Content>
                      <Select.ItemGroup>
                        {items_password_type.items.map((item) => (
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
              {isSelectClear && (
                <Alert.Root status="warning" borderRadius="md">
                  <Alert.Indicator />
                  <Alert.Description>
                    Password will be stored in plaintext in the TACACS+ config
                    file.
                  </Alert.Description>
                </Alert.Root>
              )}
              {!isSelectMavis && (
                <Field
                  required
                  invalid={!!errors.password}
                  errorText={errors.password?.message}
                  label="Password"
                  helperText="For 'crypt' type, this will be hashed with SHA-512 on the server. For 'clear', it is stored as plaintext."
                >
                  <Input
                    {...register("password", {
                      required: isSelectMavis ? false : "Password is required.",
                    })}
                    placeholder="Password"
                    type="password"
                  />
                </Field>
              )}
              <Field
                required
                invalid={!!errors.member}
                errorText={errors.member?.message}
                label="Group Membership"
                helperText="Associate the user with one or more groups to inherit their command and service access profiles."
              >
                <input
                  type="hidden"
                  {...register("member", {
                    required: "Group membership is required.",
                  })}
                />
                <Select.Root
                  collection={items_tacacs_groups}
                  size="sm"
                  multiple
                  onValueChange={(selection) => {
                    setValue("member", selection.value.join(","), {
                      shouldValidate: true,
                    })
                  }}
                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="Select TACACS groups" />
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
              </Field>
              <Field
                invalid={!!errors.description}
                errorText={errors.description?.message}
                label="Description"
                helperText="Optional descriptive notes (e.g. employee name or department)."
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
                      onCheckedChange={({ checked }) => field.onChange(checked)}
                    >
                      Generate to TACACS+ Config
                    </Checkbox>
                  </Field>
                )}
              />
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

export default AddTacacsUser
