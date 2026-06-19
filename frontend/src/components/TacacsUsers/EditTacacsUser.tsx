import {
  Alert,
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
  TacacsGroupsService,
  type TacacsUserPublic,
  TacacsUsersService,
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

interface EditTacacsUserProps {
  tacacs_user: TacacsUserPublic
}

interface TacacsUserUpdateForm {
  username: string
  password_type: string
  password: string
  member: string
  description?: string
}

const EditTacacsUser = ({ tacacs_user }: EditTacacsUserProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [isSelectMavis, setIsSelectMavis] = useState(
    tacacs_user.password_type === "mavis",
  )
  const [isSelectClear, setIsSelectClear] = useState(
    tacacs_user.password_type === "clear",
  )
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<TacacsUserUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...tacacs_user,
      description: tacacs_user.description ?? undefined,
      password_type: tacacs_user.password_type ?? undefined,
      password: "",
      member: tacacs_user.member ?? undefined,
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
  const items_password_type = createListCollection<{
    value: string
    label: string
  }>({
    items: [
      { value: "clear", label: "clear" },
      { value: "crypt", label: "crypt" },
      { value: "mavis", label: "mavis" },
    ],
  })
  const mutation = useMutation({
    mutationFn: (data: TacacsUserUpdateForm) =>
      TacacsUsersService.updateTacacsUser({
        id: tacacs_user.id,
        requestBody: data,
      }),
    onSuccess: () => {
      showSuccessToast("TacacsUser updated successfully.")
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

  const onSubmit: SubmitHandler<TacacsUserUpdateForm> = async (data) => {
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
          Edit TACACS User
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit TACACS User</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4} color="fg.muted" fontSize="sm">
              Update the user account details. Local logins support secure
              hashing (crypt) or plaintext (clear), while mavis delegates auth
              to remote servers (LDAP/AD).
            </Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.username}
                errorText={errors.username?.message}
                label="Username"
                helperText="The username is unique and cannot be modified."
              >
                <Input
                  {...register("username", {
                    required: "username is required",
                  })}
                  placeholder="username"
                  type="text"
                  disabled={true}
                />
              </Field>
              <Field
                required
                invalid={!!errors.password_type}
                errorText={errors.password_type?.message}
                label="Password Type"
                helperText="Recommended: Use 'crypt' to encrypt passwords securely on the server."
              >
                <Select.Root
                  defaultValue={
                    [
                      items_password_type.items.find(
                        (item) => item.value === tacacs_user.password_type,
                      )?.value,
                    ].filter(Boolean) as string[]
                  }
                  collection={items_password_type}
                  onValueChange={(selection) => {
                    const val = selection.value[0] ?? ""
                    setValue("password_type", val)
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
                        {["clear", "mavis", "crypt"].map((type) => (
                          <Select.Item key={type} item={type}>
                            {type}
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
                      required: isSelectMavis ? false : "password is required.",
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
                <Select.Root
                  collection={items_tacacs_groups}
                  defaultValue={
                    tacacs_user.member ? tacacs_user.member.split(",") : []
                  }
                  size="sm"
                  multiple
                  onValueChange={(selection) => {
                    setValue("member", selection.value.join(","))
                  }}
                >
                  <Select.Control>
                    <Select.Trigger>
                      <Select.ValueText placeholder="Select Tacacs Groups" />
                    </Select.Trigger>
                    <Select.IndicatorGroup>
                      <Select.ClearTrigger
                        onChange={() => {
                          setValue("member", "")
                        }}
                      />
                      <Select.Indicator />
                    </Select.IndicatorGroup>
                  </Select.Control>
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

export default EditTacacsUser
