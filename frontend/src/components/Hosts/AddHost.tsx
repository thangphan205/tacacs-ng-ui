import {
  Button,
  Collapsible,
  createListCollection,
  DialogActionTrigger,
  DialogTitle,
  Input,
  Select,
  SimpleGrid,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaPlus } from "react-icons/fa"
import { type HostCreate, HostsService } from "@/client"
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
      name: "",
      ipv4_address: "",
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

  const items_hosts = createListCollection<{ value: string; label: string }>({
    items: [],
  })
  if (hostsData && hostsData.data.length > 0) {
    hostsData.data.forEach((hostData) => {
      items_hosts.items.push({
        value: hostData.name,
        label: hostData.name,
      })
    })
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
            <Text mb={4} color="fg.muted" fontSize="sm">
              Add a network device that will authenticate against the TACACS+ server.
            </Text>
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
                  placeholder="core-switch-01"
                  type="text"
                />
              </Field>
              <SimpleGrid columns={2} gap={4} w="full">
                <Field
                  required
                  invalid={!!errors.ipv4_address}
                  errorText={errors.ipv4_address?.message}
                  label="IPv4 Address / CIDR"
                >
                  <Input
                    {...register("ipv4_address", {
                      required: "IPv4 address is required.",
                    })}
                    placeholder="192.168.1.1 or 192.168.1.0/24"
                    type="text"
                  />
                </Field>
                <Field
                  invalid={!!errors.ipv6_address}
                  errorText={errors.ipv6_address?.message}
                  label="IPv6 Address"
                >
                  <Input
                    {...register("ipv6_address")}
                    placeholder="2001:db8::1 (optional)"
                    type="text"
                  />
                </Field>
                <Field
                  required
                  invalid={!!errors.secret_key}
                  errorText={errors.secret_key?.message}
                  label="Secret Key"
                >
                  <Input
                    {...register("secret_key", {
                      required: "Secret key is required.",
                    })}
                    placeholder="Shared secret key"
                    type="password"
                  />
                </Field>
                <Field
                  invalid={!!errors.parent}
                  errorText={errors.parent?.message}
                  label="Parent Host"
                >
                  <Select.Root
                    collection={items_hosts}
                    size="sm"
                    onSelect={(selection) => {
                      setValue("parent", selection.value)
                    }}
                  >
                    <Select.Trigger>
                      <Select.ValueText placeholder="None" />
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
              <Field
                invalid={!!errors.description}
                errorText={errors.description?.message}
                label="Description"
              >
                <Input
                  {...register("description")}
                  placeholder="Optional description"
                  type="text"
                />
              </Field>
              <Collapsible.Root style={{ width: "100%" }}>
                <Collapsible.Trigger asChild>
                  <Button w="full" variant="outline" size="sm">
                    Configure Banner Messages
                  </Button>
                </Collapsible.Trigger>
                <Collapsible.Content>
                  <VStack gap={4} pt={4}>
                    <Field
                      invalid={!!errors.welcome_banner}
                      errorText={errors.welcome_banner?.message}
                      label="Welcome Banner"
                    >
                      <Textarea
                        {...register("welcome_banner")}
                        placeholder="Message shown on successful login"
                      />
                    </Field>
                    <Field
                      invalid={!!errors.reject_banner}
                      errorText={errors.reject_banner?.message}
                      label="Reject Banner"
                    >
                      <Textarea
                        {...register("reject_banner")}
                        placeholder="Message shown when access is denied"
                      />
                    </Field>
                    <Field
                      invalid={!!errors.motd_banner}
                      errorText={errors.motd_banner?.message}
                      label="MOTD Banner"
                    >
                      <Textarea
                        {...register("motd_banner")}
                        placeholder="Message of the day shown after login"
                      />
                    </Field>
                    <Field
                      invalid={!!errors.failed_authentication_banner}
                      errorText={errors.failed_authentication_banner?.message}
                      label="Failed Authentication Banner"
                    >
                      <Textarea
                        {...register("failed_authentication_banner")}
                        placeholder="Message shown on failed authentication"
                      />
                    </Field>
                  </VStack>
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
              Add Host
            </Button>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default AddHost
