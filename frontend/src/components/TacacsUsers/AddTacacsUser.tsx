import {
  Button,
  DialogActionTrigger,
  DialogTitle,
  Input,
  Select,
  Text,
  VStack,
  createListCollection,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaPlus } from "react-icons/fa"

import { TacacsGroupsService, type TacacsUserCreate, TacacsUsersService } from "@/client"
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

const AddTacacsUser = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [isSelectMavis, setIsSelectMavis] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isValid, isSubmitting },
  } = useForm<TacacsUserCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      username: "",
      description: "",
    },
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

  let items_tacacs_groups = createListCollection<{ value: string; label: string }>({ items: [] });
  if (data_groups && data_groups.data.length > 0) {
    data_groups.data.forEach((group) => {
      items_tacacs_groups.items.push({
        value: group.group_name,
        label: group.group_name,
      });
    });
  }
  const items_password_type = createListCollection<{ value: string; label: string }>({
    items: [
      { value: 'clear', label: 'clear' },
      { value: 'crypt', label: 'crypt' },
      { value: 'pbkdf2', label: 'pbkdf2' },
      { value: 'mavis', label: 'mavis' },
    ],
  });

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
          Add TacacsUser
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add TacacsUser</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Fill in the details to add a new item.</Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.username}
                errorText={errors.username?.message}
                label="Username"
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
                label="password_type"
              >
                <Select.Root
                  collection={items_password_type}
                  onSelect={(selection) => {
                    setValue("password_type", selection.value);
                    setIsSelectMavis(selection.value === "mavis");
                  }}
                  size="sm"
                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="Select password type" />
                  </Select.Trigger>
                  <Select.Positioner>
                    <Select.Content>
                      <Select.ItemGroup>
                        {["clear", "mavis", "crypt", "pbkdf2"].map((type) => (
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
              {!isSelectMavis && (
                <Field
                  required
                  invalid={!!errors.password}
                  errorText={errors.password?.message}
                  label="password"
                >
                  <Input
                    {...register("password", {
                      required: isSelectMavis ? false : "password is required.",
                    })}
                    placeholder="password"
                    type="password"
                  />
                </Field>
              )}
              <Field
                required
                invalid={!!errors.member}
                errorText={errors.member?.message}
                label="member"
              >
                <Select.Root
                  collection={items_tacacs_groups}
                  size="sm"
                  multiple
                  onValueChange={(selection) => {
                    setValue("member", selection.value.join(","));
                  }}

                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="Select Tacacs Groups" />
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
    </DialogRoot >
  )
}

export default AddTacacsUser
