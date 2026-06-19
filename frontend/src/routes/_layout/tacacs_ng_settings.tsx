import {
  Box,
  Button,
  Container,
  EmptyState,
  Flex,
  Heading,
  HStack,
  Input,
  SimpleGrid,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import {
  FiCpu,
  FiDatabase,
  FiFileText,
  FiSave,
  FiServer,
  FiSettings,
} from "react-icons/fi"

import {
  type ApiError,
  TacacsNgSettingsService,
  type TacacsNgSettingUpdate,
} from "@/client"
import PendingTacacsNgSettings from "@/components/Pending/PendingTacacsNgSettings"
import { Checkbox } from "@/components/ui/checkbox"
import { Field } from "@/components/ui/field"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

function getTacacsNgSettingsQueryOptions() {
  return {
    queryFn: () => TacacsNgSettingsService.readTacacsNgSettings(),
    queryKey: ["tacacs_ng_settings"],
  }
}

export const Route = createFileRoute("/_layout/tacacs_ng_settings")({
  component: TacacsNgSettings,
})

function TacacsNgSettingsForm() {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const [activeTab, setActiveTab] = useState("network")

  const { data: settings, isLoading } = useQuery({
    ...getTacacsNgSettingsQueryOptions(),
  })

  const {
    register,
    handleSubmit,
    reset,
    watch,
    getValues,
    control,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<TacacsNgSettingUpdate>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ipv4_enabled: true,
      ipv4_address: "0.0.0.0",
      ipv4_port: 49,
      ipv6_enabled: false,
      ipv6_address: "::",
      ipv6_port: 49,
      instances_min: 1,
      instances_max: 10,
      background: "no",
      access_logfile_destination: "",
      authentication_logfile_destination: "",
      authorization_logfile_destination: "",
      accounting_logfile_destination: "",
      login_backend: "mavis",
      user_backend: "mavis",
      pap_backend: "mavis",
      timezone: "UTC",
    },
  })

  // Watch network listen states to disable fields reactively
  const watchIpv4Enabled = watch("ipv4_enabled", true)
  const watchIpv6Enabled = watch("ipv6_enabled", false)

  useEffect(() => {
    if (settings) {
      reset(settings)
    }
  }, [settings, reset])

  const mutation = useMutation({
    mutationFn: (data: TacacsNgSettingUpdate) =>
      TacacsNgSettingsService.updateTacacsNgSettings({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("TACACS+ NG Settings updated successfully.")
      queryClient.invalidateQueries({ queryKey: ["tacacs_ng_settings"] })
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
  })

  const onSubmit: SubmitHandler<TacacsNgSettingUpdate> = async (data) => {
    mutation.mutate(data)
  }

  if (isLoading) {
    return <PendingTacacsNgSettings />
  }

  if (!settings) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSettings />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>TACACS+ NG Settings not found</EmptyState.Title>
            <EmptyState.Description>
              Settings have not been configured yet.
            </EmptyState.Description>
          </VStack>
        </EmptyState.Content>
      </EmptyState.Root>
    )
  }

  const tabs = [
    {
      id: "network",
      label: "Network & Listeners",
      icon: FiServer,
      desc: "Port mappings and network interfaces.",
    },
    {
      id: "performance",
      label: "Scaling & Performance",
      icon: FiCpu,
      desc: "Process scaling limits and run mode.",
    },
    {
      id: "backends",
      label: "Auth Backends",
      icon: FiDatabase,
      desc: "LDAP, AD, Mavis backend routing.",
    },
    {
      id: "logging",
      label: "Logging Paths",
      icon: FiFileText,
      desc: "Path destinations and timezone setup.",
    },
  ]

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <style>{`
        @keyframes slideUp {
          from { transform: translateY(15px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>

      <Flex
        direction={{ base: "column", md: "row" }}
        gap={8}
        mt={6}
        align="stretch"
      >
        {/* Left Side Tab Navigation */}
        <VStack
          w={{ base: "full", md: "260px" }}
          align="stretch"
          gap={1.5}
          borderRightWidth={{ base: 0, md: "1px" }}
          borderBottomWidth={{ base: "1px", md: 0 }}
          borderColor="border.subtle"
          pb={{ base: 4, md: 0 }}
          pr={{ base: 0, md: 6 }}
        >
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <Button
                key={tab.id}
                variant="ghost"
                justifyContent="flex-start"
                h="auto"
                py="3"
                px="4"
                bg={isActive ? "bg.subtle" : "transparent"}
                color={isActive ? "teal.fg" : "fg.muted"}
                _hover={{ bg: "bg.muted", color: "fg" }}
                onClick={() => setActiveTab(tab.id)}
                transition="all 0.2s"
                borderRadius="lg"
                borderLeftWidth={isActive ? "3px" : "0px"}
                borderLeftColor="teal.solid"
                pl={isActive ? "13px" : "4"}
              >
                <HStack gap={3} w="full" align="start">
                  <Icon
                    style={{
                      marginTop: "3px",
                      fontSize: "16px",
                      flexShrink: 0,
                    }}
                  />
                  <VStack align="start" gap={0} w="full">
                    <Text
                      fontSize="sm"
                      fontWeight={isActive ? "bold" : "semibold"}
                    >
                      {tab.label}
                    </Text>
                    <Text
                      fontSize="2xs"
                      color="fg.muted"
                      fontWeight="normal"
                      textAlign="left"
                    >
                      {tab.desc}
                    </Text>
                  </VStack>
                </HStack>
              </Button>
            )
          })}
        </VStack>

        {/* Right Side Tab Panel */}
        <Box
          flex={1}
          bg="bg.panel"
          p={6}
          borderWidth="1px"
          borderRadius="xl"
          shadow="sm"
          minH="450px"
        >
          {activeTab === "network" && (
            <VStack gap={6} align="stretch">
              <Box>
                <Heading size="sm" mb={1}>
                  Network Listeners
                </Heading>
                <Text fontSize="xs" color="fg.muted">
                  Configure binding IP addresses and port options for IPv4 and
                  IPv6 protocols.
                </Text>
              </Box>

              {/* IPv4 Configuration Block */}
              <Box p={4} borderWidth="1px" borderRadius="lg" bg="bg.subtle">
                <Flex direction="column" gap={4}>
                  <Controller
                    control={control}
                    name="ipv4_enabled"
                    render={({ field }) => (
                      <Field disabled={field.disabled} colorPalette="teal">
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={({ checked }) =>
                            field.onChange(checked)
                          }
                        >
                          Enable IPv4 Listener
                        </Checkbox>
                      </Field>
                    )}
                  />
                  <SimpleGrid
                    columns={{ base: 1, sm: 2 }}
                    gap={4}
                    opacity={watchIpv4Enabled ? 1 : 0.5}
                    transition="opacity 0.2s"
                  >
                    <Field
                      label="IPv4 Bind Address"
                      required={watchIpv4Enabled}
                      errorText={errors.ipv4_address?.message}
                      helperText="Default: 0.0.0.0 (listen on all interfaces)"
                    >
                      <Input
                        {...register("ipv4_address", {
                          required: watchIpv4Enabled
                            ? "IPv4 Address is required."
                            : false,
                        })}
                        placeholder="0.0.0.0"
                        disabled={!watchIpv4Enabled}
                      />
                    </Field>
                    <Field
                      label="IPv4 Bind Port"
                      required={watchIpv4Enabled}
                      errorText={errors.ipv4_port?.message}
                      helperText="Default standard TACACS+ port is 49"
                    >
                      <Input
                        {...register("ipv4_port", {
                          required: watchIpv4Enabled
                            ? "IPv4 Port is required."
                            : false,
                          valueAsNumber: true,
                        })}
                        type="number"
                        placeholder="49"
                        disabled={!watchIpv4Enabled}
                      />
                    </Field>
                  </SimpleGrid>
                </Flex>
              </Box>

              {/* IPv6 Configuration Block */}
              <Box p={4} borderWidth="1px" borderRadius="lg" bg="bg.subtle">
                <Flex direction="column" gap={4}>
                  <Controller
                    control={control}
                    name="ipv6_enabled"
                    render={({ field }) => (
                      <Field disabled={field.disabled} colorPalette="teal">
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={({ checked }) =>
                            field.onChange(checked)
                          }
                        >
                          Enable IPv6 Listener
                        </Checkbox>
                      </Field>
                    )}
                  />
                  <SimpleGrid
                    columns={{ base: 1, sm: 2 }}
                    gap={4}
                    opacity={watchIpv6Enabled ? 1 : 0.5}
                    transition="opacity 0.2s"
                  >
                    <Field
                      label="IPv6 Bind Address"
                      required={watchIpv6Enabled}
                      errorText={errors.ipv6_address?.message}
                      helperText="Default: :: (listen on all IPv6 interfaces)"
                    >
                      <Input
                        {...register("ipv6_address", {
                          required: watchIpv6Enabled
                            ? "IPv6 Address is required."
                            : false,
                        })}
                        placeholder="::"
                        disabled={!watchIpv6Enabled}
                      />
                    </Field>
                    <Field
                      label="IPv6 Bind Port"
                      required={watchIpv6Enabled}
                      errorText={errors.ipv6_port?.message}
                    >
                      <Input
                        {...register("ipv6_port", {
                          required: watchIpv6Enabled
                            ? "IPv6 Port is required."
                            : false,
                          valueAsNumber: true,
                        })}
                        type="number"
                        placeholder="49"
                        disabled={!watchIpv6Enabled}
                      />
                    </Field>
                  </SimpleGrid>
                </Flex>
              </Box>
            </VStack>
          )}

          {activeTab === "performance" && (
            <VStack gap={6} align="stretch">
              <Box>
                <Heading size="sm" mb={1}>
                  Daemon Performance & Scaling
                </Heading>
                <Text fontSize="xs" color="fg.muted">
                  Configure pre-fork process thresholds and daemonization
                  properties.
                </Text>
              </Box>

              <SimpleGrid columns={{ base: 1, sm: 2 }} gap={4}>
                <Field
                  label="Minimum Daemon Instances"
                  required
                  errorText={errors.instances_min?.message}
                  helperText="Pre-forked processes that spawn immediately on startup."
                >
                  <Input
                    {...register("instances_min", {
                      required: "Minimum instances is required.",
                      valueAsNumber: true,
                      min: { value: 1, message: "Must be at least 1." },
                    })}
                    type="number"
                  />
                </Field>
                <Field
                  label="Maximum Daemon Instances"
                  required
                  errorText={errors.instances_max?.message}
                  helperText="Upper limit of concurrent process instances to handle spikes."
                >
                  <Input
                    {...register("instances_max", {
                      required: "Maximum instances is required.",
                      valueAsNumber: true,
                      min: { value: 1, message: "Must be at least 1." },
                      validate: (value) =>
                        (value ?? 0) >= (getValues("instances_min") ?? 0) ||
                        "Maximum must be ≥ minimum instances.",
                    })}
                    type="number"
                  />
                </Field>
              </SimpleGrid>

              <Box p={4} borderWidth="1px" borderRadius="lg" bg="bg.subtle">
                <Controller
                  control={control}
                  name="background"
                  render={({ field }) => (
                    <Field
                      disabled={field.disabled}
                      colorPalette="teal"
                      helperText="If enabled, the TACACS+ process detaches and runs in background daemon mode."
                    >
                      <Checkbox
                        checked={field.value === "yes"}
                        onCheckedChange={({ checked }) =>
                          field.onChange(checked ? "yes" : "no")
                        }
                      >
                        Run in Background (Daemon mode)
                      </Checkbox>
                    </Field>
                  )}
                />
              </Box>
            </VStack>
          )}

          {activeTab === "backends" && (
            <VStack gap={6} align="stretch">
              <Box>
                <Heading size="sm" mb={1}>
                  Authentication Backends
                </Heading>
                <Text fontSize="xs" color="fg.muted">
                  Specify external validation mechanisms to process client
                  credentials.
                </Text>
              </Box>

              <VStack gap={4}>
                <Field
                  label="Default Login Backend"
                  errorText={errors.login_backend?.message}
                  helperText="Main backend service module used for standard logins (default: mavis)."
                >
                  <Input {...register("login_backend")} />
                </Field>
                <Field
                  label="Default User Backend"
                  errorText={errors.user_backend?.message}
                  helperText="Backend module query interface to resolve group permissions."
                >
                  <Input {...register("user_backend")} />
                </Field>
                <Field
                  label="PAP Protocol Backend"
                  errorText={errors.pap_backend?.message}
                  helperText="Backend service module resolving PAP-based connections."
                >
                  <Input {...register("pap_backend")} />
                </Field>
              </VStack>
            </VStack>
          )}

          {activeTab === "logging" && (
            <VStack gap={6} align="stretch">
              <Box>
                <Heading size="sm" mb={1}>
                  Logging Configuration
                </Heading>
                <Text fontSize="xs" color="fg.muted">
                  Set dynamic directory/file logging structures for AAA events.
                </Text>
              </Box>

              <Field
                label="Log Timezone"
                required
                errorText={errors.timezone?.message}
                helperText="IANA timezone name for log date calculations (e.g. UTC, Asia/Ho_Chi_Minh)."
              >
                <Input
                  {...register("timezone", {
                    required: "Timezone is required.",
                  })}
                  placeholder="UTC"
                />
              </Field>

              <VStack
                gap={4}
                p={4}
                borderWidth="1px"
                borderRadius="lg"
                bg="bg.subtle"
              >
                <Field
                  label="Access Logs Destination"
                  errorText={errors.access_logfile_destination?.message}
                >
                  <Input
                    {...register("access_logfile_destination")}
                    placeholder="/var/log/tac_plus/access-%Y-%m-%d.log"
                  />
                </Field>
                <Field
                  label="Authentication Logs Destination"
                  errorText={errors.authentication_logfile_destination?.message}
                >
                  <Input
                    {...register("authentication_logfile_destination")}
                    placeholder="/var/log/tac_plus/auth-%Y-%m-%d.log"
                  />
                </Field>
                <Field
                  label="Authorization Logs Destination"
                  errorText={errors.authorization_logfile_destination?.message}
                >
                  <Input
                    {...register("authorization_logfile_destination")}
                    placeholder="/var/log/tac_plus/authz-%Y-%m-%d.log"
                  />
                </Field>
                <Field
                  label="Accounting Logs Destination"
                  errorText={errors.accounting_logfile_destination?.message}
                >
                  <Input
                    {...register("accounting_logfile_destination")}
                    placeholder="/var/log/tac_plus/acct-%Y-%m-%d.log"
                  />
                </Field>
              </VStack>
            </VStack>
          )}
        </Box>
      </Flex>

      {/* Floating Vercel-style Save Changes Banner */}
      {isDirty && (
        <Box
          position="fixed"
          bottom="6"
          left={{ base: "6", md: "calc(260px + 6rem)" }}
          right="6"
          bg="bg.panel"
          borderWidth="1px"
          borderColor="teal.muted"
          p="4"
          borderRadius="xl"
          shadow="xl"
          zIndex="999"
          style={{ animation: "slideUp 0.3s ease-out" }}
        >
          <Flex align="center" justify="space-between" gap={4} wrap="wrap">
            <VStack align="start" gap={0.5}>
              <Text fontWeight="bold" fontSize="sm" color="teal.fg">
                Unsaved Changes Detected
              </Text>
              <Text fontSize="xs" color="fg.muted">
                You have modified the server settings. Save to apply them to the
                config.
              </Text>
            </VStack>
            <HStack gap={3}>
              <Button
                size="sm"
                variant="outline"
                disabled={isSubmitting}
                onClick={() => reset(settings)}
              >
                Discard
              </Button>
              <Button
                size="sm"
                type="submit"
                colorPalette="teal"
                loading={isSubmitting}
              >
                <FiSave fontSize="14px" />
                Save Changes
              </Button>
            </HStack>
          </Flex>
        </Box>
      )}
    </form>
  )
}

function TacacsNgSettings() {
  return (
    <Container maxW="full">
      <Flex direction="column" pt={6} gap={1}>
        <HStack gap={3}>
          <Box p={2} bg="teal.muted" borderRadius="lg" color="teal.fg">
            <FiSettings fontSize="22px" />
          </Box>
          <VStack align="start" gap={0}>
            <Heading size="md">TACACS+ NG Server Settings</Heading>
            <Text color="fg.muted" fontSize="xs">
              Manage system-wide listeners, scaling daemons, log storage
              locations, and local timezone.
            </Text>
          </VStack>
        </HStack>
      </Flex>
      <TacacsNgSettingsForm />
    </Container>
  )
}
