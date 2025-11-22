import {
  Button,
  Collapsible,
  DialogActionTrigger,
  DialogTitle,
  Input,
  Text,
  SimpleGrid,
  Textarea,
  VStack,
  Select,
  createListCollection
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaPlus } from "react-icons/fa"

import { type HostCreate, HostsService } from "@/client"
import type { ApiError } from "@/client/core/ApiError"
import { useQuery } from "@tanstack/react-query"
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

const AddHost = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isValid, isSubmitting },
  } = useForm<HostCreate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "demo",
      ipv4_address: "192.168.1.0/24",
      ipv6_address: "",
      secret_key: "",
      description: "",
      welcome_banner: "",
      reject_banner: "",
      motd_banner: "",
      failed_authentication_banner: "",
      parent: "",
    },
  })

  const { data: hostsData } = useQuery({
    queryKey: ["hosts"],
    queryFn: () => HostsService.readHosts({ limit: 1000 }),
  })

  const mutation = useMutation({
    mutationFn: (data: HostCreate) =>
      HostsService.createHost({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Host created successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["hosts"] })
    },
  })

  const onSubmit: SubmitHandler<HostCreate> = (data) => {
    mutation.mutate(data)
  }

  let items_hosts = createListCollection<{ value: string; label: string }>({ items: [] });
  if (hostsData && hostsData.data.length > 0) {
    hostsData.data.forEach((hostData) => {
      items_hosts.items.push({
        value: hostData.name,
        label: hostData.name,
      });
    });
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
          Add Host
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add Host</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Fill in the details to add a new item.</Text>
            <VStack gap={4} as="section">
              <Field
                required
                invalid={!!errors.name}
                errorText={errors.name?.message}
                label="Name"
              >
                <Input
                  {...register("name", {
                    required: "Name is required.",
                  })}
                  placeholder="Name"
                  type="text"
                />
              </Field>
              <SimpleGrid columns={2} gap={4} w="full">
                <Field
                  required
                  invalid={!!errors.ipv4_address}
                  errorText={errors.ipv4_address?.message}
                  label="ipv4_address"
                >
                  <Input
                    {...register("ipv4_address", {
                      required: "ipv4_address is required.",
                    })}
                    placeholder="ipv4_address"
                    type="text"
                  />
                </Field>
                <Field
                  required
                  invalid={!!errors.secret_key}
                  errorText={errors.secret_key?.message}
                  label="secret_key"
                >
                  <Input
                    {...register("secret_key", {
                      required: "secret_key is required.",
                    })}
                    placeholder="secret_key"
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
                <Field invalid={!!errors.parent} errorText={errors.parent?.message} label="parent">
                  {/* <Select {...register("parent")} placeholder="Select parent">
                    <option value="">None</option>
                    {hostsData?.data.map((host) => (
                      <option key={host.id} value={host.name}>
                        {host.name}
                      </option>
                    ))}
                  </Select> */}

                  <Select.Root
                    collection={items_hosts}
                    size="sm"
                    onSelect={(selection) => {
                      setValue("parent", selection.value);
                    }}
                  >
                    <Select.Trigger>
                      <Select.ValueText placeholder="Select Host Parent" />
                    </Select.Trigger>
                    <Select.Positioner>
                      <Select.Content>
                        <Select.ItemGroup>
                          {items_hosts.items.map((item) => (
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
              </SimpleGrid>
              <Collapsible.Root style={{ width: "100%" }}>
                <Collapsible.Trigger asChild><Button w="full" variant="outline">Configure Banner Messages</Button></Collapsible.Trigger>
                <Collapsible.Content>

                  <Field
                    invalid={!!errors.welcome_banner}
                    errorText={errors.welcome_banner?.message}
                    label="welcome_banner"
                  >
                    <Textarea
                      {...register("welcome_banner")}
                      placeholder="welcome_banner"

                    />
                  </Field>
                  <Field
                    invalid={!!errors.reject_banner}
                    errorText={errors.reject_banner?.message}
                    label="reject_banner"
                  >
                    <Textarea
                      {...register("reject_banner")}
                      placeholder="reject_banner"

                    />
                  </Field>
                  <Field
                    invalid={!!errors.motd_banner}
                    errorText={errors.motd_banner?.message}
                    label="motd_banner"
                  >
                    <Textarea
                      {...register("motd_banner")}
                      placeholder="motd_banner"

                    />
                  </Field>
                  <Field
                    invalid={!!errors.failed_authentication_banner}
                    errorText={errors.failed_authentication_banner?.message}
                    label="failed_authentication_banner"
                  >
                    <Textarea
                      {...register("failed_authentication_banner")}
                      placeholder="failed_authentication_banner"

                    />
                  </Field>

                </Collapsible.Content>
              </Collapsible.Root>

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

export default AddHost
