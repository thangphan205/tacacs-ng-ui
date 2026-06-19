import {
  Badge,
  Box,
  Button,
  Collapsible,
  createListCollection,
  DialogActionTrigger,
  DialogTitle,
  Flex,
  Grid,
  GridItem,
  Input,
  Select,
  SimpleGrid,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import {
  FiGlobe,
  FiHash,
  FiInfo,
  FiKey,
  FiLayers,
  FiLock,
  FiMessageSquare,
  FiPlus,
  FiServer,
  FiSettings,
  FiType,
} from "react-icons/fi"
import { type HostCreate, HostsService } from "@/client"
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

interface FieldGuideItem {
  icon: React.ElementType
  label: string
  description: string
  example?: string
  required?: boolean
}

const fieldGuideItems: FieldGuideItem[] = [
  {
    icon: FiType,
    label: "Name",
    description:
      "A unique identifier for this network device. Used in the generated TACACS+ config and as reference across the UI.",
    example: "core-switch-01, dc1-fw-primary",
    required: true,
  },
  {
    icon: FiGlobe,
    label: "IPv4 Address / CIDR",
    description:
      "The management IP address or subnet (CIDR) of the device. CIDR notation allows a range of devices to share the same TACACS+ key.",
    example: "10.0.1.1 or 10.0.1.0/24",
    required: true,
  },
  {
    icon: FiHash,
    label: "IPv6 Address",
    description:
      "Optional IPv6 management address. Set this if your device connects to the TACACS+ server over IPv6.",
    example: "2001:db8::1",
  },
  {
    icon: FiKey,
    label: "Secret Key",
    description:
      "The shared secret between this device and the TACACS+ server. Must match the key configured on the network device exactly (case-sensitive).",
    example: "MyS3cretK3y!",
    required: true,
  },
  {
    icon: FiLayers,
    label: "Parent Host",
    description:
      "Optionally inherit settings from an existing host. The child host will use its parent's configuration as a fallback.",
  },
  {
    icon: FiInfo,
    label: "Description",
    description:
      "Free-text note for your reference. Not included in the generated config — useful for documenting location, role, or owner.",
  },
  {
    icon: FiSettings,
    label: "Generate to Config",
    description:
      "When enabled, this host will be included in the generated TACACS+ daemon configuration file. Disable to keep the record without activating it.",
  },
  {
    icon: FiMessageSquare,
    label: "Banner Messages",
    description:
      "Optional banners displayed to users during authentication: Welcome (on success), Reject (on deny), MOTD (after login), and Failed Authentication.",
  },
]

const FieldGuideCard = ({ item }: { item: FieldGuideItem }) => {
  const Icon = item.icon
  return (
    <Box>
      <Flex align="flex-start" gap={2.5}>
        <Box
          mt={0.5}
          p={1}
          bg="teal.muted"
          color="teal.fg"
          borderRadius="md"
          flexShrink={0}
        >
          <Icon size={12} />
        </Box>
        <Box>
          <Flex align="center" gap={1.5} mb={0.5}>
            <Text fontSize="xs" fontWeight="semibold" color="fg">
              {item.label}
            </Text>
            {item.required && (
              <Badge
                colorPalette="red"
                variant="subtle"
                size="sm"
                fontSize="2xs"
                px={1}
                lineHeight="1.4"
              >
                Required
              </Badge>
            )}
          </Flex>
          <Text fontSize="xs" color="fg.muted" lineHeight="1.5">
            {item.description}
          </Text>
          {item.example && (
            <Text fontSize="2xs" color="fg.muted/70" mt={0.5} fontFamily="mono">
              e.g. {item.example}
            </Text>
          )}
        </Box>
      </Flex>
    </Box>
  )
}

const AddHost = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
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
      generate_config: true,
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
      size="xl"
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button value="add-item" my={4}>
          <FiPlus fontSize="16px" />
          Add Host
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add Host</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              {/* Left Column: Form inputs */}
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Add a network device that will authenticate against the TACACS+
                  server.
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
              </GridItem>

              {/* Right Column: Field Guide */}
              <GridItem
                bg="bg.muted/60"
                p={5}
                borderRadius="xl"
                borderWidth="1px"
                borderColor="border.subtle"
                height="fit-content"
              >
                <Flex align="center" gap={2} mb={1}>
                  <Box p={1.5} bg="teal.muted" color="teal.fg" borderRadius="md">
                    <FiServer size={16} />
                  </Box>
                  <Text fontSize="xs" fontWeight="bold" textTransform="uppercase" letterSpacing="wider" color="teal.fg">
                    Field Guide
                  </Text>
                </Flex>
                <Text fontSize="xs" color="fg.muted" mb={4}>
                  Learn what each field means and how it maps to the TACACS+ daemon configuration.
                </Text>

                <VStack gap={3.5} align="stretch">
                  {fieldGuideItems.map((item) => (
                    <FieldGuideCard key={item.label} item={item} />
                  ))}
                </VStack>

                <Box
                  mt={4}
                  p={3}
                  bg="teal.muted/40"
                  borderRadius="md"
                  borderWidth="1px"
                  borderColor="teal.muted"
                >
                  <Flex align="center" gap={1.5} mb={1}>
                    <FiLock size={11} />
                    <Text fontSize="2xs" fontWeight="semibold" color="teal.fg">
                      How it works
                    </Text>
                  </Flex>
                  <Text fontSize="2xs" color="fg.muted" lineHeight="1.5">
                    When you save a host with "Generate to Config" enabled, the system creates a{" "}
                    <Text as="span" fontFamily="mono" fontWeight="medium">host</Text> block in the
                    TACACS+ daemon config using the Name, IPv4 Address, and Secret Key you provide.
                  </Text>
                </Box>
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

