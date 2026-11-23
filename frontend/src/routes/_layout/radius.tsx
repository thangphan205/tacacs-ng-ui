import {
  Alert,
  Badge,
  Box,
  Button,
  Container,
  EmptyState,
  Flex,
  Heading,
  HStack,
  Input,
  Link,
  SimpleGrid,
  Table,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link as RouterLink } from "@tanstack/react-router"
import { useEffect } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import { FiExternalLink, FiRadio, FiSave } from "react-icons/fi"

import type { ApiError } from "@/api"
import {
  HostsService,
  type TacacsNgSettingPublic,
  TacacsNgSettingsService,
} from "@/client"
import PageHeader from "@/components/Common/PageHeader"
import PendingTacacsNgSettings from "@/components/Pending/PendingTacacsNgSettings"
import { Checkbox } from "@/components/ui/checkbox"
import { Field } from "@/components/ui/field"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/radius")({
  component: Radius,
})

const DEFAULT_RADIUS_AUTH_PORT = 1812
const DEFAULT_RADIUS_ACCT_PORT = 1813
const HOSTS_SHOWN = 100
const RADIUS_DOCS_URL =
  "https://github.com/thangphan205/tacacs-ng-ui/blob/main/docs/en/radius.md"

// Only these fields are sent: the settings PUT is partial, so the rest of
// TacacsNgSetting (owned by the NG Settings page) is left untouched.
interface RadiusForm {
  radius_enabled: boolean
  radius_auth_port: number
  radius_acct_port: number
  radius_dictionary_extra: string
}

// A textarea needs a string; the API sends null for "no custom dictionary".
function toForm(settings: TacacsNgSettingPublic): RadiusForm {
  return {
    radius_enabled: !!settings.radius_enabled,
    radius_auth_port: settings.radius_auth_port ?? DEFAULT_RADIUS_AUTH_PORT,
    radius_acct_port: settings.radius_acct_port ?? DEFAULT_RADIUS_ACCT_PORT,
    radius_dictionary_extra: settings.radius_dictionary_extra ?? "",
  }
}

function RadiusSettingsForm({ settings }: { settings: TacacsNgSettingPublic }) {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()

  const {
    register,
    handleSubmit,
    reset,
    watch,
    getValues,
    control,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<RadiusForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: toForm(settings),
  })

  useEffect(() => {
    reset(toForm(settings))
  }, [settings, reset])

  const watchRadiusEnabled = watch("radius_enabled")
  const radiusPortsMoved =
    watch("radius_auth_port") !== DEFAULT_RADIUS_AUTH_PORT ||
    watch("radius_acct_port") !== DEFAULT_RADIUS_ACCT_PORT

  const mutation = useMutation({
    mutationFn: (data: RadiusForm) =>
      TacacsNgSettingsService.updateTacacsNgSettings({
        tacacsNgSettingUpdate: data,
      }),
    onSuccess: () => {
      showSuccessToast("RADIUS settings updated successfully.")
      queryClient.invalidateQueries({ queryKey: ["tacacs_ng_settings"] })
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
  })

  const onSubmit: SubmitHandler<RadiusForm> = async (data) => {
    await mutation.mutateAsync(data).catch(() => undefined)
  }

  return (
    <Box
      as="form"
      onSubmit={handleSubmit(onSubmit)}
      bg="bg.panel"
      p={6}
      borderWidth="1px"
      borderRadius="xl"
      shadow="sm"
    >
      <VStack gap={6} align="stretch">
        <Box>
          <Heading size="sm" mb={1}>
            Settings
          </Heading>
          <Text fontSize="xs" color="fg.muted">
            Serve RADIUS from the same server, for devices that do not speak
            TACACS+ (for example MikroTik). Users, groups, profiles and rulesets
            are shared with TACACS+; a profile returns RADIUS attributes with
            lines such as{" "}
            <code>set radius[MikroTik:MikroTik-Group] = full</code> inside{" "}
            <code>if (aaa.protocol == radius)</code>. Takes effect after
            Generate and Activate.
          </Text>
        </Box>

        <Box p={4} borderWidth="1px" borderRadius="lg" bg="bg.subtle">
          <Controller
            control={control}
            name="radius_enabled"
            render={({ field }) => (
              <Field
                disabled={field.disabled}
                colorPalette="teal"
                helperText={
                  field.value
                    ? "RADIUS listeners, the RADIUS dictionary and the hosts' RADIUS secrets are written to the generated config."
                    : "Off: the generated config has no RADIUS at all. Host RADIUS secrets and the custom dictionary are kept and come back when it is turned on."
                }
              >
                <Checkbox
                  checked={!!field.value}
                  onCheckedChange={({ checked }) => field.onChange(!!checked)}
                >
                  Enable RADIUS
                </Checkbox>
              </Field>
            )}
          />
        </Box>

        {watchRadiusEnabled && (
          <>
            <SimpleGrid columns={{ base: 1, sm: 2 }} gap={4}>
              <Field
                label="Authentication Port (UDP)"
                required
                invalid={!!errors.radius_auth_port}
                errorText={errors.radius_auth_port?.message}
                helperText="Standard: 1812"
              >
                <Input
                  {...register("radius_auth_port", {
                    required: "Authentication port is required.",
                    valueAsNumber: true,
                    min: { value: 1, message: "Use 1-65535." },
                    max: { value: 65535, message: "Use 1-65535." },
                    validate: (value) =>
                      value !== getValues("radius_acct_port") ||
                      "Must differ from the accounting port.",
                  })}
                  type="number"
                  placeholder="1812"
                />
              </Field>
              <Field
                label="Accounting Port (UDP)"
                required
                invalid={!!errors.radius_acct_port}
                errorText={errors.radius_acct_port?.message}
                helperText="Standard: 1813"
              >
                <Input
                  {...register("radius_acct_port", {
                    required: "Accounting port is required.",
                    valueAsNumber: true,
                    min: { value: 1, message: "Use 1-65535." },
                    max: { value: 65535, message: "Use 1-65535." },
                    deps: ["radius_auth_port"],
                  })}
                  type="number"
                  placeholder="1813"
                />
              </Field>
            </SimpleGrid>

            <Alert.Root
              status={radiusPortsMoved ? "warning" : "info"}
              size="sm"
              borderRadius="md"
            >
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title>
                  {radiusPortsMoved
                    ? "Update the published ports too"
                    : "UDP ports"}
                </Alert.Title>
                <Alert.Description>
                  docker-compose.yml publishes 1812/udp and 1813/udp from the
                  backend container.
                  {radiusPortsMoved &&
                    " Change those mappings to match, or devices cannot reach the new ports."}{" "}
                  RADIUS identifies a device by its source address, so the
                  published port must keep it (Docker Desktop rewrites it; Linux
                  hosts keep it).
                </Alert.Description>
              </Alert.Content>
            </Alert.Root>

            <Field
              label="Custom RADIUS Dictionary"
              invalid={!!errors.radius_dictionary_extra}
              errorText={errors.radius_dictionary_extra?.message}
              helperText="Optional. Extra vendor attributes, added after the built-in dictionary (RFC attributes plus Cisco, Juniper, Fortinet, PaloAlto, Aruba, Huawei, MikroTik and Microsoft). Only radius.dictionary blocks are allowed."
            >
              <Textarea
                {...register("radius_dictionary_extra")}
                fontFamily="mono"
                fontSize="xs"
                rows={8}
                placeholder={
                  "radius.dictionary Ubiquiti 41112 {\n    attribute Ubiquiti-Admin-Role 1 string\n}"
                }
              />
            </Field>
          </>
        )}

        <HStack gap={3} justify="flex-end">
          <Button
            size="sm"
            variant="outline"
            disabled={!isDirty || isSubmitting}
            onClick={() => reset(toForm(settings))}
          >
            Discard
          </Button>
          <Button
            size="sm"
            type="submit"
            colorPalette="teal"
            disabled={!isDirty}
            loading={isSubmitting}
          >
            <FiSave fontSize="14px" />
            Save Changes
          </Button>
        </HStack>
      </VStack>
    </Box>
  )
}

/**
 * What the saved settings put in the generated config, and what RADIUS uses
 * from the shared entities. Read-only: hosts, users and profiles are edited on
 * their own pages, which serve TACACS+ and RADIUS alike.
 */
function RadiusReadiness({ settings }: { settings: TacacsNgSettingPublic }) {
  const { data, isLoading } = useQuery({
    queryKey: ["hosts", { has_radius_secret: true, limit: HOSTS_SHOWN }],
    queryFn: () =>
      HostsService.readHosts({ has_radius_secret: true, limit: HOSTS_SHOWN }),
  })
  const hosts = data?.data ?? []
  const count = data?.count ?? 0
  const address = settings.ipv4_address || "0.0.0.0"

  return (
    <Box bg="bg.panel" p={6} borderWidth="1px" borderRadius="xl" shadow="sm">
      <VStack gap={6} align="stretch">
        <Box>
          <Heading size="sm" mb={1}>
            In the generated config
          </Heading>
          <Text fontSize="xs" color="fg.muted">
            From the saved settings. Generate and Activate on{" "}
            <Link asChild color="teal.fg">
              <RouterLink to="/tacacs_configs" search={{ page: 1 }}>
                TACACS Configs
              </RouterLink>
            </Link>{" "}
            to apply changes.
          </Text>
        </Box>

        <HStack gap={2} wrap="wrap">
          <Badge colorPalette="teal" variant="subtle">
            Authentication {address}:{settings.radius_auth_port}/udp
          </Badge>
          <Badge colorPalette="teal" variant="subtle">
            Accounting {address}:{settings.radius_acct_port}/udp
          </Badge>
          <Badge
            colorPalette={settings.radius_dictionary_extra ? "teal" : "gray"}
            variant="subtle"
          >
            {settings.radius_dictionary_extra
              ? "Custom dictionary"
              : "Built-in dictionary only"}
          </Badge>
        </HStack>

        <Box>
          <Flex justify="space-between" align="baseline" mb={2} gap={4}>
            <Heading size="xs">Hosts with a RADIUS secret ({count})</Heading>
            <Link asChild fontSize="xs" color="teal.fg">
              <RouterLink to="/hosts" search={{ page: 1 }}>
                Manage hosts
              </RouterLink>
            </Link>
          </Flex>
          {isLoading ? null : hosts.length === 0 ? (
            <EmptyState.Root size="sm">
              <EmptyState.Content>
                <EmptyState.Description>
                  No host has a RADIUS secret of its own, so RADIUS is answered
                  only for hosts that inherit one through their parent. Set a
                  RADIUS Secret on the host to accept RADIUS from it.
                </EmptyState.Description>
              </EmptyState.Content>
            </EmptyState.Root>
          ) : (
            <Box borderWidth="1px" borderRadius="lg" overflow="hidden">
              <Table.Root size="sm">
                <Table.Header bg="bg.muted">
                  <Table.Row>
                    <Table.ColumnHeader>Name</Table.ColumnHeader>
                    <Table.ColumnHeader>IPv4 Address</Table.ColumnHeader>
                    <Table.ColumnHeader>IPv6 Address</Table.ColumnHeader>
                    <Table.ColumnHeader>Protocols</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {hosts.map((host) => (
                    <Table.Row key={host.id}>
                      <Table.Cell fontWeight="medium">
                        <Link asChild color="teal.fg">
                          <RouterLink
                            to="/hosts"
                            search={{ page: 1, search: host.name }}
                          >
                            {host.name}
                          </RouterLink>
                        </Link>
                      </Table.Cell>
                      <Table.Cell>{host.ipv4_address || "—"}</Table.Cell>
                      <Table.Cell>{host.ipv6_address || "—"}</Table.Cell>
                      <Table.Cell>
                        <HStack gap={1}>
                          {host.secret_key && (
                            <Badge size="sm" variant="outline">
                              TACACS+
                            </Badge>
                          )}
                          <Badge size="sm" colorPalette="teal">
                            RADIUS
                          </Badge>
                        </HStack>
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Box>
          )}
          {count > hosts.length && (
            <Text fontSize="xs" color="fg.muted" mt={2}>
              Showing the first {hosts.length} of {count}.
            </Text>
          )}
        </Box>

        <Alert.Root status="info" size="sm" borderRadius="md">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>Password types</Alert.Title>
            <Alert.Description>
              <Link asChild color="teal.fg">
                <RouterLink to="/tacacs_users" search={{ page: 1 }}>
                  Users
                </RouterLink>
              </Link>{" "}
              with password type crypt (hashed) can sign in over RADIUS with PAP
              only. Devices that use CHAP or MS-CHAP, such as MikroTik RouterOS
              (MS-CHAPv2), need users with password type clear.
            </Alert.Description>
          </Alert.Content>
        </Alert.Root>

        <Text fontSize="xs" color="fg.muted">
          Return attributes from a profile with <b>Add RADIUS Attribute</b> in
          its menu on{" "}
          <Link asChild color="teal.fg">
            <RouterLink to="/profiles" search={{ page: 1 }}>
              Profiles
            </RouterLink>
          </Link>
          . RADIUS lines appear on TACACS Logs with the protocol filter.{" "}
          <Link href={RADIUS_DOCS_URL} target="_blank" color="teal.fg">
            RADIUS guide <FiExternalLink />
          </Link>
        </Text>
      </VStack>
    </Box>
  )
}

function RadiusContent() {
  const { data: settings, isLoading } = useQuery({
    queryKey: ["tacacs_ng_settings"],
    queryFn: () => TacacsNgSettingsService.readTacacsNgSettings(),
  })

  if (isLoading) {
    return <PendingTacacsNgSettings />
  }

  if (!settings) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiRadio />
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

  return (
    <VStack gap={6} align="stretch" mt={6} pb={6}>
      <RadiusSettingsForm settings={settings} />
      {settings.radius_enabled && <RadiusReadiness settings={settings} />}
    </VStack>
  )
}

function Radius() {
  return (
    <Container maxW="full">
      <PageHeader
        title="RADIUS"
        description="RADIUS served by the same tac_plus-ng, for devices that do not speak TACACS+."
        icon={FiRadio}
      />
      <RadiusContent />
    </Container>
  )
}
