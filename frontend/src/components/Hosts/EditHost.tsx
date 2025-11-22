import {
  Button,
  ButtonGroup,
  Collapsible,
  DialogActionTrigger,
  Input,
  SimpleGrid,
  Select,
  Text,
  VStack,
  Textarea,
  createListCollection,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"

import { type ApiError, type HostPublic, HostsService } from "@/client"
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
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog"
import { Field } from "../ui/field"

interface EditHostProps {
  host: HostPublic
}

interface HostUpdateForm {
  name: string
  ipv4_address?: string
  ipv6_address?: string
  secret_key: string
  description?: string
  welcome_banner?: string
  reject_banner?: string
  motd_banner?: string
  failed_authentication_banner?: string
  parent?: string
}



const EditHost = ({ host }: EditHostProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<HostUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...host,
      name: host.name ?? undefined,
      ipv4_address: host.ipv4_address ?? undefined,
      ipv6_address: host.ipv6_address ?? undefined,
      secret_key: host.secret_key ?? undefined,
      description: host.description ?? undefined,
      welcome_banner: host.welcome_banner ?? undefined,
      reject_banner: host.reject_banner ?? undefined,
      motd_banner: host.motd_banner ?? undefined,
      failed_authentication_banner: host.failed_authentication_banner ?? undefined,
      parent: host.parent ?? undefined,
    },
  })

  const { data: hostsData } = useQuery({
    queryKey: ["hosts"],
    queryFn: () => HostsService.readHosts({ limit: 1000 }),
  })

  const mutation = useMutation({
    mutationFn: (data: HostUpdateForm) =>
      HostsService.updateHost({ id: host.id, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Host updated successfully.")
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

  const onSubmit: SubmitHandler<HostUpdateForm> = async (data) => {
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
      size={{ base: "xs", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost">
          <FaExchangeAlt fontSize="16px" />
          Edit Host
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit Host</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Update the item details below.</Text>
            <VStack gap={4} as="section">
              <Field
                required
                invalid={!!errors.name}
                errorText={errors.name?.message}
                label="name"
              >
                <Input
                  {...register("name", {
                    required: "Title is required",
                  })}
                  placeholder="name"
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
                  <VStack gap={4} pt={4}>
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
                  </VStack>
                </Collapsible.Content>
              </Collapsible.Root>
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

export default EditHost
