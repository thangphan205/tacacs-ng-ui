import {
  Box,
  Button,
  Code,
  Collapsible,
  createListCollection,
  DialogActionTrigger,
  DialogTitle,
  Flex,
  Grid,
  GridItem,
  Heading,
  Input,
  Select,
  SimpleGrid,
  Text,
  Textarea,
  VStack,
  Tabs,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import { FiBookOpen, FiPlus } from "react-icons/fi"
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
    watch,
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

  const secretKey = watch("secret_key") || "<your_secret_key>"
  const serverIp = typeof window !== "undefined" ? (window.location.hostname || "192.168.1.100") : "192.168.1.100"

  const [copiedText, setCopiedText] = useState(false)
  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedText(true)
    setTimeout(() => setCopiedText(false), 2000)
  }

  const ciscoSnippet = `! Configure the TACACS+ Server
tacacs server TACACS_SERVER
 address ipv4 ${serverIp}
 key ${secretKey}
!
! Enable AAA and define server group
aaa new-model
aaa group server tacacs+ TACACS_GROUP
 server name TACACS_SERVER
!
! Apply authentication and authorization
aaa authentication login default group TACACS_GROUP local
aaa authorization exec default group TACACS_GROUP local
aaa accounting exec default start-stop group TACACS_GROUP`

  const juniperSnippet = `# Configure TACACS+ server and key
set system tacplus-server ${serverIp} secret "${secretKey}"
# Configure authentication order
set system authentication-order [ tacplus password ]
# Create a template user for authorization
set system login user template-user uid 2000 class super-user`

  const aristaSnippet = `! Configure the TACACS+ server
tacacs-server host ${serverIp} key ${secretKey}
!
! Apply AAA settings
aaa group server tacacs+ TACACS_GROUP
 server ${serverIp}
!
aaa authentication login default group TACACS_GROUP local
aaa authorization exec default group TACACS_GROUP local`

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

              {/* Right Column: Dynamic Configuration Instructions */}
              <GridItem
                bg="bg.muted/60"
                p={5}
                borderRadius="xl"
                borderWidth="1px"
                borderColor="border.subtle"
                height="fit-content"
              >
                <Flex align="center" gap={2} mb={3}>
                  <Box p={1.5} bg="teal.muted" color="teal.fg" borderRadius="md">
                    <FiBookOpen fontSize="16px" />
                  </Box>
                  <Heading size="xs" fontWeight="bold" textTransform="uppercase" letterSpacing="wider" color="teal.fg">
                    Configuration Guide
                  </Heading>
                </Flex>
                <Text fontSize="xs" color="fg.muted" mb={4}>
                  Use these real-time generated commands on your device to establish authentication with this TACACS+ server.
                </Text>

                <Tabs.Root defaultValue="cisco" size="sm" variant="subtle" colorPalette="teal">
                  <Tabs.List mb={3}>
                    <Tabs.Trigger value="cisco" fontSize="xs">Cisco IOS</Tabs.Trigger>
                    <Tabs.Trigger value="juniper" fontSize="xs">Juniper Junos</Tabs.Trigger>
                    <Tabs.Trigger value="arista" fontSize="xs">Arista EOS</Tabs.Trigger>
                  </Tabs.List>

                  <Tabs.Content value="cisco">
                    <Box position="relative" mt={1}>
                      <Code
                        display="block"
                        whiteSpace="pre"
                        fontSize="2xs"
                        p={3}
                        borderRadius="md"
                        bg="bg.panel"
                        borderWidth="1px"
                        maxH="280px"
                        overflowY="auto"
                        fontFamily="mono"
                      >
                        {ciscoSnippet}
                      </Code>
                      <Button
                        size="2xs"
                        variant="subtle"
                        position="absolute"
                        top={2}
                        right={2}
                        onClick={() => handleCopy(ciscoSnippet)}
                        colorPalette="teal"
                      >
                        {copiedText ? "Copied!" : "Copy"}
                      </Button>
                    </Box>
                  </Tabs.Content>

                  <Tabs.Content value="juniper">
                    <Box position="relative" mt={1}>
                      <Code
                        display="block"
                        whiteSpace="pre"
                        fontSize="2xs"
                        p={3}
                        borderRadius="md"
                        bg="bg.panel"
                        borderWidth="1px"
                        maxH="280px"
                        overflowY="auto"
                        fontFamily="mono"
                      >
                        {juniperSnippet}
                      </Code>
                      <Button
                        size="2xs"
                        variant="subtle"
                        position="absolute"
                        top={2}
                        right={2}
                        onClick={() => handleCopy(juniperSnippet)}
                        colorPalette="teal"
                      >
                        {copiedText ? "Copied!" : "Copy"}
                      </Button>
                    </Box>
                  </Tabs.Content>

                  <Tabs.Content value="arista">
                    <Box position="relative" mt={1}>
                      <Code
                        display="block"
                        whiteSpace="pre"
                        fontSize="2xs"
                        p={3}
                        borderRadius="md"
                        bg="bg.panel"
                        borderWidth="1px"
                        maxH="280px"
                        overflowY="auto"
                        fontFamily="mono"
                      >
                        {aristaSnippet}
                      </Code>
                      <Button
                        size="2xs"
                        variant="subtle"
                        position="absolute"
                        top={2}
                        right={2}
                        onClick={() => handleCopy(aristaSnippet)}
                        colorPalette="teal"
                      >
                        {copiedText ? "Copied!" : "Copy"}
                      </Button>
                    </Box>
                  </Tabs.Content>
                </Tabs.Root>
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
