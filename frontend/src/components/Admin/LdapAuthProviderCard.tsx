import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Flex,
  Heading,
  HStack,
  Input,
  NativeSelect,
  Separator,
  SimpleGrid,
  Switch,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import {
  LuDownload,
  LuPlus,
  LuSave,
  LuServer,
  LuShieldCheck,
  LuTrash2,
  LuWifi,
} from "react-icons/lu"

import type { ApiError } from "@/api"
import {
  AdminService,
  type AuthProviderConfigPublic,
  type LdapTestAuthResponse,
  type LdapTestConnectionResponse,
} from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ProviderConfig {
  provider: string
  enabled: boolean
  config: Record<string, string>
  secret_is_set: boolean
}

interface LdapServerRow {
  url: string
  priority: number
}

interface LdapPreset {
  label: string
  username_attr: string
  unique_id_attr: string
  email_attr: string
  full_name_attr: string
  user_search_filter: string
  group_search_filter: string
  group_member_attr: string
}

const DEFAULT_PROVIDER = "freeipa"

// Through the generated client, so errors arrive as ApiError: handleError
// shows the backend's detail, and a 401 logs out like everywhere else.
function toStringConfig(
  cfg: Record<string, unknown> | undefined,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(cfg ?? {}).map(([k, v]) => [k, v == null ? "" : String(v)]),
  )
}

function toProviderConfig(data: AuthProviderConfigPublic): ProviderConfig {
  return { ...data, config: toStringConfig(data.config) }
}

async function fetchLdapProvider(): Promise<ProviderConfig> {
  return toProviderConfig(
    await AdminService.getAuthProvider({ provider: "ldap" }),
  )
}

// Presets come from the backend, which also falls back to them for any field
// left empty — one definition, not two that can drift apart.
async function fetchLdapPresets(): Promise<Record<string, LdapPreset>> {
  const presets: Record<
    string,
    Record<string, string>
  > = await AdminService.getLdapPresets()
  return presets as unknown as Record<string, LdapPreset>
}

async function saveLdapProvider(payload: {
  enabled?: boolean
  config?: Record<string, string>
  secret?: string
}): Promise<ProviderConfig> {
  return toProviderConfig(
    await AdminService.updateAuthProvider({
      provider: "ldap",
      authProviderConfigUpdate: payload,
    }),
  )
}

function parseServersFromConfig(cfg: Record<string, string>): LdapServerRow[] {
  if (cfg.servers_json) {
    try {
      const parsed = JSON.parse(cfg.servers_json)
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed.map((item, idx) => ({
          url: String(item.url ?? item.host ?? ""),
          priority: Number(item.priority ?? idx + 1),
        }))
      }
    } catch {
      // fall back to hosts string
    }
  }
  if (cfg.hosts) {
    const parts = cfg.hosts
      .split(/[\s,;]+/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (parts.length > 0) {
      return parts.map((url, idx) => ({ url, priority: idx + 1 }))
    }
  }
  return [{ url: "ldaps://ipa01.example.com:636", priority: 1 }]
}

const LdapAuthProviderCard = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()

  const { data, isLoading } = useQuery({
    queryKey: ["auth-provider", "ldap"],
    queryFn: fetchLdapProvider,
  })
  const { data: presets } = useQuery({
    queryKey: ["ldap-presets"],
    queryFn: fetchLdapPresets,
    staleTime: Number.POSITIVE_INFINITY,
  })

  const [providerType, setProviderType] = useState(DEFAULT_PROVIDER)
  const [servers, setServers] = useState<LdapServerRow[]>([
    { url: "ldaps://ipa01.example.com:636", priority: 1 },
  ])
  const [baseDn, setBaseDn] = useState("")
  const [userBaseDn, setUserBaseDn] = useState("")
  const [groupBaseDn, setGroupBaseDn] = useState("")
  const [bindDn, setBindDn] = useState("")
  const [bindPassword, setBindPassword] = useState("")
  const [usernameAttr, setUsernameAttr] = useState("")
  const [uniqueIdAttr, setUniqueIdAttr] = useState("")
  const [emailAttr, setEmailAttr] = useState("")
  const [fullNameAttr, setFullNameAttr] = useState("")
  const [userSearchFilter, setUserSearchFilter] = useState("")
  const [fallbackEmailDomain, setFallbackEmailDomain] = useState("")
  const [allowEmailLink, setAllowEmailLink] = useState(false)
  const [requiredGroup, setRequiredGroup] = useState("")
  const [groupSearchFilter, setGroupSearchFilter] = useState("")
  const [groupMemberAttr, setGroupMemberAttr] = useState("")
  const [startTls, setStartTls] = useState(false)
  const [allowInsecure, setAllowInsecure] = useState(false)
  const [verifyTls, setVerifyTls] = useState(true)
  const [caCertPem, setCaCertPem] = useState("")
  const [connectTimeout, setConnectTimeout] = useState("5")
  const [receiveTimeout, setReceiveTimeout] = useState("10")
  const [initialized, setInitialized] = useState(false)

  // Diagnostic state
  const [connTestResult, setConnTestResult] =
    useState<LdapTestConnectionResponse | null>(null)
  const [testUsername, setTestUsername] = useState("")
  const [testPassword, setTestPassword] = useState("")
  const [authTestResult, setAuthTestResult] =
    useState<LdapTestAuthResponse | null>(null)

  useEffect(() => {
    if (data && presets && !initialized) {
      const cfg = data.config ?? {}
      const pType =
        cfg.provider_type && presets[cfg.provider_type]
          ? cfg.provider_type
          : DEFAULT_PROVIDER
      const preset = presets[pType]
      setProviderType(pType)
      setServers(parseServersFromConfig(cfg))
      setBaseDn(cfg.base_dn ?? "")
      setUserBaseDn(cfg.user_base_dn ?? "")
      setGroupBaseDn(cfg.group_base_dn ?? "")
      setBindDn(cfg.bind_dn ?? "")
      setUsernameAttr(cfg.username_attr ?? preset.username_attr)
      setUniqueIdAttr(cfg.unique_id_attr ?? preset.unique_id_attr)
      setFallbackEmailDomain(cfg.fallback_email_domain ?? "")
      setAllowEmailLink(cfg.allow_email_link === "true")
      setEmailAttr(cfg.email_attr ?? preset.email_attr)
      setFullNameAttr(cfg.full_name_attr ?? preset.full_name_attr)
      setUserSearchFilter(cfg.user_search_filter ?? preset.user_search_filter)
      setRequiredGroup(cfg.required_group ?? "")
      setGroupSearchFilter(
        cfg.group_search_filter ?? preset.group_search_filter,
      )
      setGroupMemberAttr(cfg.group_member_attr ?? preset.group_member_attr)
      setStartTls(cfg.start_tls === "true")
      setAllowInsecure(cfg.allow_insecure === "true")
      setVerifyTls(cfg.verify_tls !== "false")
      setCaCertPem(cfg.ca_cert_pem ?? "")
      setConnectTimeout(cfg.connect_timeout ?? "5")
      setReceiveTimeout(cfg.receive_timeout ?? "10")
      setInitialized(true)
    }
  }, [data, presets, initialized])

  // Mirrors the backend: ldap:// (explicit or bare host) with no StartTLS.
  const hasCleartextServer =
    !startTls &&
    servers.some((s) => {
      const url = s.url.trim().toLowerCase()
      return url.length > 0 && !url.startsWith("ldaps://")
    })

  const buildConfigPayload = (): Record<string, string> => {
    const cleanServers = servers
      .map((s, idx) => ({
        url: s.url.trim(),
        priority:
          Number.isFinite(s.priority) && s.priority > 0 ? s.priority : idx + 1,
      }))
      .filter((s) => s.url.length > 0)

    return {
      provider_type: providerType,
      hosts: cleanServers.map((s) => s.url).join(", "),
      servers_json: JSON.stringify(cleanServers),
      base_dn: baseDn.trim(),
      user_base_dn: userBaseDn.trim(),
      group_base_dn: groupBaseDn.trim(),
      bind_dn: bindDn.trim(),
      username_attr: usernameAttr.trim(),
      unique_id_attr: uniqueIdAttr.trim(),
      fallback_email_domain: fallbackEmailDomain.trim(),
      allow_email_link: allowEmailLink ? "true" : "false",
      email_attr: emailAttr.trim(),
      full_name_attr: fullNameAttr.trim(),
      user_search_filter: userSearchFilter.trim(),
      required_group: requiredGroup.trim(),
      group_search_filter: groupSearchFilter.trim(),
      group_member_attr: groupMemberAttr.trim(),
      start_tls: startTls ? "true" : "false",
      allow_insecure: allowInsecure ? "true" : "false",
      verify_tls: verifyTls ? "true" : "false",
      ca_cert_pem: caCertPem.trim(),
      connect_timeout: connectTimeout.trim() || "5",
      receive_timeout: receiveTimeout.trim() || "10",
    }
  }

  const handleProviderChange = (newType: string) => {
    setProviderType(newType)
    const preset = presets?.[newType]
    if (preset) {
      setUsernameAttr(preset.username_attr)
      setUniqueIdAttr(preset.unique_id_attr)
      setEmailAttr(preset.email_attr)
      setFullNameAttr(preset.full_name_attr)
      setUserSearchFilter(preset.user_search_filter)
      setGroupSearchFilter(preset.group_search_filter)
      setGroupMemberAttr(preset.group_member_attr)
    }
  }

  const importMavisMutation = useMutation({
    mutationFn: (): Promise<Record<string, string>> =>
      AdminService.importLdapFromMavis(),
    onSuccess: (imported) => {
      const pType = imported.provider_type || "freeipa"
      handleProviderChange(pType)
      if (imported.hosts) {
        setServers(parseServersFromConfig({ hosts: imported.hosts }))
      }
      if (imported.base_dn) setBaseDn(imported.base_dn)
      if (imported.bind_dn) setBindDn(imported.bind_dn)
      if (imported.username_attr) setUsernameAttr(imported.username_attr)
      if (imported.user_search_filter)
        setUserSearchFilter(imported.user_search_filter)
      showSuccessToast(
        "Imported connection settings from MAVIS. Enter the Bind Password and save.",
      )
    },
    onError: (err: ApiError) => handleError(err),
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      saveLdapProvider({
        enabled: data?.enabled,
        config: buildConfigPayload(),
        secret: bindPassword || undefined,
      }),
    onSuccess: () => {
      showSuccessToast("LDAP authentication configuration saved.")
      setBindPassword("")
      queryClient.invalidateQueries({ queryKey: ["auth-provider", "ldap"] })
      queryClient.invalidateQueries({ queryKey: ["auth-providers-status"] })
    },
    onError: (err: ApiError) => handleError(err),
  })

  const toggleMutation = useMutation({
    // Only flips the switch: unsaved form edits are saved with Save, not here.
    mutationFn: (enabled: boolean) => saveLdapProvider({ enabled }),
    onSuccess: (updated) => {
      showSuccessToast(
        `LDAP authentication ${updated.enabled ? "enabled" : "disabled"}.`,
      )
      queryClient.invalidateQueries({ queryKey: ["auth-provider", "ldap"] })
      queryClient.invalidateQueries({ queryKey: ["auth-providers-status"] })
    },
    onError: (err: ApiError) => handleError(err),
  })

  const testConnectionMutation = useMutation({
    mutationFn: () =>
      AdminService.testLdapConnectionRoute({
        ldapTestConnectionRequest: {
          config: buildConfigPayload(),
          secret: bindPassword || undefined,
        },
      }),
    onSuccess: (result) => setConnTestResult(result),
    onError: (err: ApiError) => handleError(err),
  })

  const testAuthMutation = useMutation({
    mutationFn: () =>
      AdminService.testLdapAuthRoute({
        ldapTestAuthRequest: {
          username: testUsername.trim(),
          password: testPassword,
          config: buildConfigPayload(),
          secret: bindPassword || undefined,
        },
      }),
    onSuccess: (result) => setAuthTestResult(result),
    onError: (err: ApiError) => handleError(err),
  })

  const addServerRow = () => {
    setServers((prev) => [...prev, { url: "", priority: prev.length + 1 }])
  }

  const removeServerRow = (index: number) => {
    setServers((prev) => prev.filter((_, idx) => idx !== index))
  }

  const updateServerRow = (index: number, patch: Partial<LdapServerRow>) => {
    setServers((prev) =>
      prev.map((row, idx) => (idx === index ? { ...row, ...patch } : row)),
    )
  }

  return (
    <Card.Root variant="outline">
      <Card.Header pb={4}>
        <Flex
          justify="space-between"
          align={{ base: "flex-start", sm: "center" }}
          direction={{ base: "column", sm: "row" }}
          gap={4}
        >
          <HStack gap={3.5} align="flex-start">
            <Flex
              w={10}
              h={10}
              borderRadius="lg"
              bg="bg.muted"
              borderWidth="1px"
              align="center"
              justify="center"
              fontSize="xl"
              color="teal.600"
              flexShrink={0}
              mt={0.5}
            >
              <LuServer />
            </Flex>
            <Box>
              <HStack gap={2.5} wrap="wrap">
                <Heading size="md">LDAP / Active Directory</Heading>
                <Badge
                  size="sm"
                  variant="subtle"
                  colorPalette={data?.enabled ? "green" : "gray"}
                >
                  {data?.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </HStack>
              <Text fontSize="sm" color="fg.muted" mt={1}>
                Authenticate Web UI users against FreeIPA, Active Directory, or
                OpenLDAP. Web UI permissions (Superuser vs Read-Only) are
                managed locally in Admin → Users Management.
              </Text>
            </Box>
          </HStack>

          <HStack
            gap={2.5}
            alignSelf={{ base: "flex-start", sm: "center" }}
            flexShrink={0}
            wrap="wrap"
          >
            <Button
              size="xs"
              variant="outline"
              loading={importMavisMutation.isPending}
              onClick={() => importMavisMutation.mutate()}
            >
              <LuDownload />
              Prefill from MAVIS
            </Button>
            {!isLoading && (
              <HStack
                gap={3}
                px={3}
                py={2}
                borderRadius="lg"
                bg="bg.subtle"
                borderWidth="1px"
              >
                <Text fontSize="xs" fontWeight="medium" color="fg.muted">
                  {data?.enabled ? "Active on login" : "Inactive"}
                </Text>
                <Switch.Root
                  colorPalette="teal"
                  checked={!!data?.enabled}
                  disabled={toggleMutation.isPending}
                  onCheckedChange={(e) => toggleMutation.mutate(e.checked)}
                >
                  <Switch.HiddenInput aria-label="Toggle LDAP authentication" />
                  <Switch.Control />
                </Switch.Root>
              </HStack>
            )}
          </HStack>
        </Flex>
      </Card.Header>

      <Separator />

      <Card.Body pt={5}>
        <VStack align="stretch" gap={5}>
          {/* 1. Provider Type */}
          <Box>
            <Text fontSize="xs" mb={1} fontWeight="medium">
              LDAP Directory Provider Type
            </Text>
            <NativeSelect.Root size="sm">
              <NativeSelect.Field
                value={providerType}
                onChange={(e) => handleProviderChange(e.target.value)}
              >
                {Object.entries(presets ?? {}).map(([key, preset]) => (
                  <option key={key} value={key}>
                    {preset.label}
                  </option>
                ))}
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
            <Text fontSize="xs" mt={1} color="fg.muted">
              Selecting a provider populates default user/group attributes and
              search filters below. All fields remain customizable.
            </Text>
          </Box>

          {/* 2. Multiple LDAP Servers & Priority Failover */}
          <Box>
            <HStack justify="space-between" mb={2}>
              <Box>
                <Text fontSize="xs" fontWeight="medium">
                  LDAP / LDAPS Servers (Automatic Failover)
                </Text>
                <Text fontSize="xs" color="fg.muted">
                  Tried in ascending priority order (1 = Primary, 2 =
                  Secondary). Failover triggers only when a server is
                  unreachable.
                </Text>
              </Box>
              <Button size="xs" variant="outline" onClick={addServerRow}>
                <LuPlus />
                Add Server
              </Button>
            </HStack>

            <VStack align="stretch" gap={2}>
              {servers.map((srv, idx) => (
                <HStack key={idx} gap={2}>
                  <Input
                    size="sm"
                    flex="1"
                    placeholder="ldaps://ipa01.example.com:636 or ldap://dc01.example.com:389"
                    value={srv.url}
                    onChange={(e) =>
                      updateServerRow(idx, { url: e.target.value })
                    }
                  />
                  <Box w="110px">
                    <Input
                      size="sm"
                      type="number"
                      min={1}
                      max={100}
                      placeholder="Priority"
                      value={srv.priority}
                      onChange={(e) =>
                        updateServerRow(idx, {
                          priority: Number(e.target.value) || idx + 1,
                        })
                      }
                    />
                  </Box>
                  {servers.length > 1 && (
                    <Button
                      size="xs"
                      variant="ghost"
                      colorPalette="red"
                      onClick={() => removeServerRow(idx)}
                    >
                      <LuTrash2 />
                    </Button>
                  )}
                </HStack>
              ))}
            </VStack>
          </Box>

          {/* 3. Directory Base DN & Bind Credentials */}
          <SimpleGrid columns={{ base: 1, md: 2 }} gap={3}>
            <Box>
              <Text fontSize="xs" mb={1} fontWeight="medium">
                Base DN
              </Text>
              <Input
                size="sm"
                placeholder="dc=example,dc=com"
                value={baseDn}
                onChange={(e) => setBaseDn(e.target.value)}
              />
            </Box>
            <Box>
              <Text fontSize="xs" mb={1} fontWeight="medium">
                User Base DN (Optional)
              </Text>
              <Input
                size="sm"
                placeholder="Defaults to Base DN (e.g. cn=users,cn=accounts,dc=example,dc=com)"
                value={userBaseDn}
                onChange={(e) => setUserBaseDn(e.target.value)}
              />
            </Box>
            <Box>
              <Text fontSize="xs" mb={1} fontWeight="medium">
                Service Account Bind DN
              </Text>
              <Input
                size="sm"
                placeholder="uid=svc-tacacs,cn=users,cn=accounts,dc=example,dc=com"
                value={bindDn}
                onChange={(e) => setBindDn(e.target.value)}
              />
            </Box>
            <Box>
              <Text fontSize="xs" mb={1} fontWeight="medium">
                Bind Password{" "}
                {data?.secret_is_set && (
                  <Text as="span" color="green.500">
                    (configured)
                  </Text>
                )}
              </Text>
              <Input
                size="sm"
                type="password"
                placeholder={
                  data?.secret_is_set
                    ? "Leave blank to keep existing"
                    : "Enter bind password"
                }
                value={bindPassword}
                onChange={(e) => setBindPassword(e.target.value)}
              />
            </Box>
          </SimpleGrid>

          {/* 4. Optional Custom Required LDAP Group */}
          <Box p={3} borderWidth="1px" borderRadius="md" bg="bg.subtle">
            <Heading size="xs" mb={2}>
              Access Control — Optional Custom Group Gate
            </Heading>
            <SimpleGrid columns={{ base: 1, md: 2 }} gap={3}>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Required LDAP Group Name or DN (Optional)
                </Text>
                <Input
                  size="sm"
                  placeholder="e.g. tacacs-ui-users or cn=network-admins,cn=groups,dc=example,dc=com"
                  value={requiredGroup}
                  onChange={(e) => setRequiredGroup(e.target.value)}
                />
                <Text fontSize="xs" mt={1} color="fg.muted">
                  Leave blank to allow any valid user under Base DN. When set,
                  only members of this custom group can log in.
                </Text>
              </Box>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Group Base DN (Optional)
                </Text>
                <Input
                  size="sm"
                  placeholder="Defaults to Base DN (e.g. cn=groups,cn=accounts,dc=example,dc=com)"
                  value={groupBaseDn}
                  onChange={(e) => setGroupBaseDn(e.target.value)}
                />
              </Box>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Group Search Filter
                </Text>
                <Input
                  size="sm"
                  placeholder="(&(objectClass=groupOfNames)(cn={group}))"
                  value={groupSearchFilter}
                  onChange={(e) => setGroupSearchFilter(e.target.value)}
                />
              </Box>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Group Membership Attributes
                </Text>
                <Input
                  size="sm"
                  placeholder="member,uniqueMember,memberUid"
                  value={groupMemberAttr}
                  onChange={(e) => setGroupMemberAttr(e.target.value)}
                />
              </Box>
            </SimpleGrid>
          </Box>

          {/* 5. Schema & User Attributes */}
          <Box>
            <Heading size="xs" mb={2}>
              Schema & User Attribute Mapping
            </Heading>
            <SimpleGrid columns={{ base: 1, md: 3 }} gap={3} mb={3}>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Username Attribute
                </Text>
                <Input
                  size="sm"
                  placeholder="uid or sAMAccountName"
                  value={usernameAttr}
                  onChange={(e) => setUsernameAttr(e.target.value)}
                />
              </Box>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Email Attribute
                </Text>
                <Input
                  size="sm"
                  placeholder="mail"
                  value={emailAttr}
                  onChange={(e) => setEmailAttr(e.target.value)}
                />
              </Box>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Full Name Attribute
                </Text>
                <Input
                  size="sm"
                  placeholder="cn or displayName"
                  value={fullNameAttr}
                  onChange={(e) => setFullNameAttr(e.target.value)}
                />
              </Box>
            </SimpleGrid>
            <Box>
              <Text fontSize="xs" mb={1} fontWeight="medium">
                User Search Filter
              </Text>
              <Input
                size="sm"
                placeholder="(&(objectClass=posixAccount)(uid={username}))"
                value={userSearchFilter}
                onChange={(e) => setUserSearchFilter(e.target.value)}
              />
              <Text fontSize="xs" mt={1} color="fg.muted">
                Use {"{username}"} (or %s) as placeholder for the login
                username.
              </Text>
            </Box>
            <SimpleGrid columns={{ base: 1, md: 2 }} gap={3} mt={3}>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Unique ID Attribute
                </Text>
                <Input
                  size="sm"
                  placeholder="objectGUID, ipaUniqueID or entryUUID"
                  value={uniqueIdAttr}
                  onChange={(e) => setUniqueIdAttr(e.target.value)}
                />
                <Text fontSize="xs" mt={1} color="fg.muted">
                  Immutable ID the local account is linked to, so a renamed or
                  re-created username never inherits someone else&apos;s
                  account. Leave blank to link on the username.
                </Text>
              </Box>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Fallback Email Domain (Optional)
                </Text>
                <Input
                  size="sm"
                  placeholder="e.g. corp.example.com"
                  value={fallbackEmailDomain}
                  onChange={(e) => setFallbackEmailDomain(e.target.value)}
                />
                <Text fontSize="xs" mt={1} color="fg.muted">
                  Used as username@domain for entries without a valid email.
                  Blank: such users are refused.
                </Text>
              </Box>
            </SimpleGrid>
            <Box mt={3}>
              <Checkbox
                checked={allowEmailLink}
                onCheckedChange={({ checked }) =>
                  setAllowEmailLink(Boolean(checked))
                }
              >
                Link existing local accounts by email
              </Checkbox>
              <Text fontSize="xs" mt={1} color="fg.muted">
                Off: a directory user whose email already belongs to a local
                account is refused. On: that account is linked on first LDAP
                sign-in — enable only if users cannot edit their own email in
                the directory. Superuser accounts are never linked.
              </Text>
            </Box>
          </Box>

          {/* 6. TLS / SSL & Timeouts */}
          <Box>
            <Heading size="xs" mb={2}>
              TLS / Certificates & Timeouts
            </Heading>
            <HStack gap={6} mb={3} wrap="wrap">
              <Checkbox
                checked={startTls}
                onCheckedChange={({ checked }) => setStartTls(Boolean(checked))}
              >
                Use StartTLS (on ldap:// connections)
              </Checkbox>
              <Checkbox
                checked={verifyTls}
                onCheckedChange={({ checked }) =>
                  setVerifyTls(Boolean(checked))
                }
              >
                Validate Server TLS Certificate
              </Checkbox>
            </HStack>
            {hasCleartextServer && (
              <Alert.Root status="warning" size="sm" mb={3}>
                <Alert.Indicator />
                <Alert.Content>
                  <Alert.Description>
                    A plain ldap:// server without StartTLS sends the service
                    account's password and every user's password unencrypted.
                    Use ldaps:// or StartTLS.
                  </Alert.Description>
                  <Checkbox
                    mt={2}
                    checked={allowInsecure}
                    onCheckedChange={({ checked }) =>
                      setAllowInsecure(Boolean(checked))
                    }
                  >
                    Allow unencrypted connections (trusted network only)
                  </Checkbox>
                </Alert.Content>
              </Alert.Root>
            )}
            <SimpleGrid columns={{ base: 1, md: 2 }} gap={3} mb={3}>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Connect Timeout (seconds)
                </Text>
                <Input
                  size="sm"
                  type="number"
                  min={1}
                  max={60}
                  value={connectTimeout}
                  onChange={(e) => setConnectTimeout(e.target.value)}
                />
              </Box>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Request Timeout (seconds)
                </Text>
                <Input
                  size="sm"
                  type="number"
                  min={1}
                  max={120}
                  value={receiveTimeout}
                  onChange={(e) => setReceiveTimeout(e.target.value)}
                />
              </Box>
            </SimpleGrid>
            <Box>
              <Text fontSize="xs" mb={1} fontWeight="medium">
                Custom Internal CA Certificate (PEM, Optional)
              </Text>
              <Textarea
                size="sm"
                rows={3}
                fontFamily="mono"
                placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
                value={caCertPem}
                onChange={(e) => setCaCertPem(e.target.value)}
              />
            </Box>
          </Box>

          {/* 7. Diagnostic Testing */}
          <Box p={3} borderWidth="1px" borderRadius="md">
            <HStack justify="space-between" mb={3} wrap="wrap" gap={2}>
              <Heading size="xs">Diagnostic & Failover Testing</Heading>
              <Button
                size="xs"
                variant="outline"
                loading={testConnectionMutation.isPending}
                onClick={() => testConnectionMutation.mutate()}
              >
                <LuWifi />
                Test Servers & Failover
              </Button>
            </HStack>

            {connTestResult && (
              <Alert.Root
                status={connTestResult.ok ? "success" : "error"}
                mb={3}
                borderRadius="md"
              >
                <Alert.Indicator />
                <Alert.Content>
                  <Alert.Title>{connTestResult.message}</Alert.Title>
                  <Alert.Description>
                    <VStack align="stretch" gap={1} mt={2}>
                      {(connTestResult.servers ?? []).map((s, idx) => (
                        <HStack key={idx} gap={2} fontSize="xs" wrap="wrap">
                          <Badge colorPalette={s.ok ? "green" : "red"}>
                            {s.ok ? "OK" : "FAIL"}
                          </Badge>
                          <Text fontWeight="medium">
                            [Priority {s.priority}] {s.server}
                          </Text>
                          {s.latency_ms != null && (
                            <Text color="fg.muted">({s.latency_ms} ms)</Text>
                          )}
                          {s.error && <Text color="red.500">— {s.error}</Text>}
                        </HStack>
                      ))}
                    </VStack>
                  </Alert.Description>
                </Alert.Content>
              </Alert.Root>
            )}

            <SimpleGrid columns={{ base: 1, md: 3 }} gap={2} alignItems="end">
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Test LDAP Username
                </Text>
                <Input
                  size="sm"
                  placeholder="jdoe"
                  value={testUsername}
                  onChange={(e) => setTestUsername(e.target.value)}
                />
              </Box>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  Test LDAP Password
                </Text>
                <Input
                  size="sm"
                  type="password"
                  placeholder="Password"
                  value={testPassword}
                  onChange={(e) => setTestPassword(e.target.value)}
                />
              </Box>
              <Button
                size="sm"
                variant="outline"
                disabled={!testUsername.trim() || !testPassword}
                loading={testAuthMutation.isPending}
                onClick={() => testAuthMutation.mutate()}
              >
                <LuShieldCheck />
                Test User Login
              </Button>
            </SimpleGrid>

            {authTestResult && (
              <Alert.Root
                status={authTestResult.ok ? "success" : "error"}
                mt={3}
                borderRadius="md"
              >
                <Alert.Indicator />
                <Alert.Content>
                  <Alert.Title>{authTestResult.message}</Alert.Title>
                  <Alert.Description fontSize="xs">
                    {authTestResult.server_used && (
                      <Text>
                        Server: {authTestResult.server_used}
                        {authTestResult.failover_occurred
                          ? " (via failover)"
                          : ""}
                      </Text>
                    )}
                    {authTestResult.user_dn && (
                      <Text>DN: {authTestResult.user_dn}</Text>
                    )}
                    {authTestResult.email && (
                      <Text>
                        Resolved Email: {authTestResult.email}
                        {authTestResult.full_name
                          ? ` (${authTestResult.full_name})`
                          : ""}
                      </Text>
                    )}
                    {authTestResult.required_group && (
                      <Text>
                        Required Group ({authTestResult.required_group}):{" "}
                        {authTestResult.group_check_passed
                          ? "Passed"
                          : "Denied"}
                      </Text>
                    )}
                  </Alert.Description>
                </Alert.Content>
              </Alert.Root>
            )}
          </Box>

          {/* 8. Save Action */}
          {!isLoading && (
            <>
              <Separator />
              <Flex justify="space-between" align="center" wrap="wrap" gap={3}>
                <Text fontSize="xs" color="fg.muted">
                  Save directory connection settings and attribute mapping.
                </Text>
                <Button
                  size="sm"
                  colorPalette="teal"
                  variant="solid"
                  loading={saveMutation.isPending}
                  onClick={() => saveMutation.mutate()}
                >
                  <LuSave />
                  Save Changes
                </Button>
              </Flex>
            </>
          )}
        </VStack>
      </Card.Body>
    </Card.Root>
  )
}

export default LdapAuthProviderCard
