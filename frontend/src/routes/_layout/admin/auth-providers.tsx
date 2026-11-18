import {
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Container,
  Flex,
  Grid,
  Heading,
  HStack,
  Separator,
  SimpleGrid,
  Switch,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { type ReactNode, useState } from "react"
import { FaMicrosoft } from "react-icons/fa"
import { FcGoogle } from "react-icons/fc"
import {
  LuCheck,
  LuFingerprint,
  LuKeyRound,
  LuLock,
  LuServer,
  LuShield,
  LuShieldCheck,
  LuUserCheck,
} from "react-icons/lu"

import { apiBaseUrl } from "@/api"
import AuthProviderCard, {
  type FieldDef,
} from "@/components/Admin/AuthProviderCard"
import LdapAuthProviderCard from "@/components/Admin/LdapAuthProviderCard"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTitle,
} from "@/components/ui/dialog"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/admin/auth-providers")({
  component: AuthProvidersPage,
})

type ProviderId =
  | "google"
  | "keycloak"
  | "microsoft"
  | "ldap"
  | "passkey"
  | "password"

// Prefilled in the form; the backend derives the same value if it is left blank.
const redirectUriField = (provider: string, where: string): FieldDef => {
  const uri = `${window.location.origin}/api/v1/oauth/${provider}/callback`
  return {
    key: "redirect_uri",
    label: "Authorized Redirect URI",
    placeholder: uri,
    defaultValue: uri,
    copyable: true,
    mono: true,
    hint: `Prefilled from this site's URL. Register this exact callback URI in ${where}.`,
  }
}

const googleFields: FieldDef[] = [
  {
    key: "client_id",
    label: "Client ID",
    placeholder: "1234567890-abc.apps.googleusercontent.com",
    mono: true,
  },
  redirectUriField("google", "your Google Cloud OAuth 2.0 Client"),
]

const keycloakFields: FieldDef[] = [
  {
    key: "server_url",
    label: "Keycloak Base URL",
    placeholder: "https://sso.example.com",
    hint: "Base URL of your Keycloak server (without /realms/...).",
  },
  {
    key: "realm",
    label: "Realm",
    placeholder: "tacacs",
  },
  {
    key: "client_id",
    label: "Client ID",
    placeholder: "tacacs-ng-ui",
    mono: true,
  },
  redirectUriField("keycloak", "your Keycloak client (Valid redirect URIs)"),
]

const microsoftFields: FieldDef[] = [
  {
    key: "tenant",
    label: "Directory (Tenant) ID",
    placeholder: "common, organizations, consumers, or your Tenant UUID",
    defaultValue: "common",
    mono: true,
    hint: "Use a specific Tenant UUID to restrict sign-in to a single organization, or 'common' for multi-tenant.",
  },
  {
    key: "client_id",
    label: "Application (Client) ID",
    placeholder: "00000000-0000-0000-0000-000000000000",
    mono: true,
  },
  redirectUriField(
    "microsoft",
    "your Microsoft Entra App Registration (Authentication → Web)",
  ),
]

function adminHeader() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("access_token")}`,
  }
}

async function fetchProvider(provider: string) {
  const res = await fetch(
    `${apiBaseUrl()}/api/v1/admin/auth-providers/${provider}`,
    { headers: adminHeader() },
  )
  if (!res.ok) throw new Error("Failed to fetch provider config")
  return res.json() as Promise<{
    provider: string
    enabled: boolean
    config: Record<string, string>
    secret_is_set: boolean
  }>
}

async function saveProvider(
  provider: string,
  payload: {
    enabled?: boolean
    config?: Record<string, string>
    secret?: string
  },
) {
  const res = await fetch(
    `${apiBaseUrl()}/api/v1/admin/auth-providers/${provider}`,
    { method: "PUT", headers: adminHeader(), body: JSON.stringify(payload) },
  )
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail ?? "Save failed")
  }
  return res.json() as Promise<{
    provider: string
    enabled: boolean
    config: Record<string, string>
    secret_is_set: boolean
  }>
}

interface NavItemDef {
  id: ProviderId
  name: string
  subtitle: string
  icon: ReactNode
  iconColor?: string
  enabled?: boolean
}

function ProviderNavButton({
  item,
  selected,
  onSelect,
}: {
  item: NavItemDef
  selected: boolean
  onSelect: () => void
}) {
  return (
    <Box
      as="button"
      onClick={onSelect}
      w="full"
      textAlign="left"
      px={3}
      py={2.5}
      borderRadius="lg"
      borderWidth="1px"
      borderColor={selected ? "teal.500" : "transparent"}
      bg={selected ? "teal.subtle" : "transparent"}
      _hover={{
        bg: selected ? "teal.subtle" : "bg.subtle",
      }}
      transition="all 0.15s ease"
      cursor="pointer"
    >
      <HStack justify="space-between" gap={3}>
        <HStack gap={3} minW={0}>
          <Flex
            w={8}
            h={8}
            borderRadius="md"
            bg={selected ? "bg" : "bg.muted"}
            borderWidth="1px"
            align="center"
            justify="center"
            fontSize="md"
            color={item.iconColor}
            flexShrink={0}
          >
            {item.icon}
          </Flex>
          <Box minW={0}>
            <Text
              fontSize="sm"
              fontWeight={selected ? "semibold" : "medium"}
              truncate
            >
              {item.name}
            </Text>
            <Text fontSize="xs" color="fg.muted" truncate>
              {item.subtitle}
            </Text>
          </Box>
        </HStack>

        {item.enabled !== undefined && (
          <Badge
            size="xs"
            variant={item.enabled ? "subtle" : "outline"}
            colorPalette={item.enabled ? "green" : "gray"}
            flexShrink={0}
          >
            {item.enabled ? "On" : "Off"}
          </Badge>
        )}
      </HStack>
    </Box>
  )
}

function AuthProvidersPage() {
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const [selectedProvider, setSelectedProvider] = useState<ProviderId>("google")
  const [passkeyDialogOpen, setPasskeyDialogOpen] = useState(false)

  const { data: googleData } = useQuery({
    queryKey: ["auth-provider", "google"],
    queryFn: () => fetchProvider("google"),
  })
  const { data: keycloakData } = useQuery({
    queryKey: ["auth-provider", "keycloak"],
    queryFn: () => fetchProvider("keycloak"),
  })
  const { data: microsoftData } = useQuery({
    queryKey: ["auth-provider", "microsoft"],
    queryFn: () => fetchProvider("microsoft"),
  })
  const { data: ldapData } = useQuery({
    queryKey: ["auth-provider", "ldap"],
    queryFn: () => fetchProvider("ldap"),
  })
  const { data: passkeyData, isLoading: passkeyLoading } = useQuery({
    queryKey: ["auth-provider", "passkey"],
    queryFn: () => fetchProvider("passkey"),
  })

  const togglePasskeyMutation = useMutation({
    mutationFn: (enabled: boolean) => saveProvider("passkey", { enabled }),
    onSuccess: (updated) => {
      showSuccessToast(
        `Passkeys (WebAuthn) ${updated.enabled ? "enabled" : "disabled"}.`,
      )
      queryClient.invalidateQueries({ queryKey: ["auth-provider", "passkey"] })
      queryClient.invalidateQueries({ queryKey: ["auth-providers-status"] })
      if (updated.enabled) setPasskeyDialogOpen(true)
    },
    onError: (err: Error) => handleError(err as never),
  })

  const disablePasswordMutation = useMutation({
    mutationFn: () =>
      saveProvider("passkey", {
        enabled: true,
        config: { ...passkeyData?.config, allow_password_login: "false" },
      }),
    onSuccess: () => {
      showSuccessToast(
        "Password login disabled. Users must use Passkey or SSO.",
      )
      queryClient.invalidateQueries({ queryKey: ["auth-provider", "passkey"] })
      queryClient.invalidateQueries({ queryKey: ["auth-providers-status"] })
      setPasskeyDialogOpen(false)
    },
    onError: (err: Error) => handleError(err as never),
  })

  const enablePasswordMutation = useMutation({
    mutationFn: () =>
      saveProvider("passkey", {
        config: { ...passkeyData?.config, allow_password_login: "true" },
      }),
    onSuccess: () => {
      showSuccessToast("Local password login re-enabled.")
      queryClient.invalidateQueries({ queryKey: ["auth-provider", "passkey"] })
      queryClient.invalidateQueries({ queryKey: ["auth-providers-status"] })
    },
    onError: (err: Error) => handleError(err as never),
  })

  const passwordLoginDisabled =
    passkeyData?.config?.allow_password_login === "false"
  const localPasswordEnabled = !passwordLoginDisabled

  if (!currentUser?.is_superuser) {
    return <Text p={8}>Access denied.</Text>
  }

  const ssoItems: NavItemDef[] = [
    {
      id: "google",
      name: "Google OAuth",
      subtitle: "Google Workspace & Cloud",
      icon: <FcGoogle />,
      enabled: googleData?.enabled,
    },
    {
      id: "keycloak",
      name: "Keycloak OIDC",
      subtitle: "OpenID Connect realm",
      icon: <LuShield />,
      iconColor: "blue.500",
      enabled: keycloakData?.enabled,
    },
    {
      id: "microsoft",
      name: "Microsoft Entra ID",
      subtitle: "Azure AD / Microsoft 365",
      icon: <FaMicrosoft />,
      iconColor: "blue.600",
      enabled: microsoftData?.enabled,
    },
  ]

  const directoryItems: NavItemDef[] = [
    {
      id: "ldap",
      name: "LDAP / Active Directory",
      subtitle: "FreeIPA, AD, OpenLDAP",
      icon: <LuServer />,
      iconColor: "teal.600",
      enabled: ldapData?.enabled,
    },
  ]

  const builtinItems: NavItemDef[] = [
    {
      id: "passkey",
      name: "Passkeys (WebAuthn)",
      subtitle: "FIDO2 & biometric login",
      icon: <LuFingerprint />,
      iconColor: "purple.500",
      enabled: passkeyData?.enabled,
    },
    {
      id: "password",
      name: "Local Password",
      subtitle: "Email & password login",
      icon: <LuKeyRound />,
      iconColor: "orange.500",
      enabled: localPasswordEnabled,
    },
  ]

  const allItems = [...ssoItems, ...directoryItems, ...builtinItems]
  const activeCount = allItems.filter((i) => i.enabled).length

  return (
    <Container maxW="full" pb={10}>
      {/* Page Header */}
      <Flex
        pt={6}
        pb={5}
        justify="space-between"
        align={{ base: "flex-start", md: "center" }}
        direction={{ base: "column", md: "row" }}
        gap={3}
      >
        <HStack gap={3.5} align="flex-start">
          <Flex
            w={10}
            h={10}
            borderRadius="lg"
            bg="teal.muted"
            color="teal.fg"
            align="center"
            justify="center"
            fontSize="xl"
            flexShrink={0}
            mt={0.5}
          >
            <LuShieldCheck />
          </Flex>
          <Box>
            <HStack gap={2.5} wrap="wrap">
              <Heading size="md">Authentication Providers</Heading>
              <Badge size="sm" colorPalette="teal" variant="subtle">
                {activeCount} of {allItems.length} Active
              </Badge>
            </HStack>
            <Text fontSize="sm" color="fg.muted" mt={0.5}>
              Configure Single Sign-On (OAuth / OIDC), LDAP directory servers,
              WebAuthn passkeys, and local password sign-in policies for the Web
              UI.
            </Text>
          </Box>
        </HStack>
      </Flex>

      {/* Master-Detail Grid */}
      <Grid
        templateColumns={{ base: "1fr", lg: "280px minmax(0, 1fr)" }}
        gap={6}
        alignItems="start"
      >
        {/* Left Navigation Sidebar */}
        <Card.Root variant="outline" p={2.5}>
          <VStack align="stretch" gap={4}>
            <Box>
              <Text
                fontSize="2xs"
                fontWeight="bold"
                textTransform="uppercase"
                letterSpacing="wider"
                color="fg.muted"
                px={3}
                py={1.5}
              >
                Single Sign-On (OAuth / OIDC)
              </Text>
              <VStack align="stretch" gap={1}>
                {ssoItems.map((item) => (
                  <ProviderNavButton
                    key={item.id}
                    item={item}
                    selected={selectedProvider === item.id}
                    onSelect={() => setSelectedProvider(item.id)}
                  />
                ))}
              </VStack>
            </Box>

            <Separator />

            <Box>
              <Text
                fontSize="2xs"
                fontWeight="bold"
                textTransform="uppercase"
                letterSpacing="wider"
                color="fg.muted"
                px={3}
                py={1.5}
              >
                Directory Services
              </Text>
              <VStack align="stretch" gap={1}>
                {directoryItems.map((item) => (
                  <ProviderNavButton
                    key={item.id}
                    item={item}
                    selected={selectedProvider === item.id}
                    onSelect={() => setSelectedProvider(item.id)}
                  />
                ))}
              </VStack>
            </Box>

            <Separator />

            <Box>
              <Text
                fontSize="2xs"
                fontWeight="bold"
                textTransform="uppercase"
                letterSpacing="wider"
                color="fg.muted"
                px={3}
                py={1.5}
              >
                Built-In & Passwordless
              </Text>
              <VStack align="stretch" gap={1}>
                {builtinItems.map((item) => (
                  <ProviderNavButton
                    key={item.id}
                    item={item}
                    selected={selectedProvider === item.id}
                    onSelect={() => setSelectedProvider(item.id)}
                  />
                ))}
              </VStack>
            </Box>
          </VStack>
        </Card.Root>

        {/* Right Detail Panel */}
        <Box maxW={selectedProvider === "ldap" ? "full" : "3xl"} w="full">
          {selectedProvider === "google" && (
            <AuthProviderCard
              provider="google"
              secretAfter="client_id"
              title="Google OAuth"
              description="Allow users to sign in with their Google Workspace or personal Google accounts via OAuth 2.0."
              icon={<FcGoogle />}
              fields={googleFields}
              setupNotes={[
                "Open Google Cloud Console → APIs & Services → Credentials.",
                "Create an OAuth 2.0 Client ID (Web application) and paste the Authorized Redirect URI above.",
                "Copy the generated Client ID and Client Secret into this form, save, and toggle the provider on.",
              ]}
            />
          )}

          {selectedProvider === "keycloak" && (
            <AuthProviderCard
              provider="keycloak"
              secretAfter="client_id"
              title="Keycloak OIDC"
              description="Authenticate users against a self-hosted Keycloak realm using OpenID Connect (Authorization Code flow)."
              icon={
                <Box color="blue.500">
                  <LuShield />
                </Box>
              }
              fields={keycloakFields}
              setupNotes={[
                "In your Keycloak Realm, create an OpenID Connect client with Client Authentication enabled.",
                "Add the Authorized Redirect URI above to Valid redirect URIs in Keycloak.",
                "Copy the Client Secret from the Credentials tab in Keycloak and save below.",
              ]}
            />
          )}

          {selectedProvider === "microsoft" && (
            <AuthProviderCard
              provider="microsoft"
              secretAfter="client_id"
              title="Microsoft Entra ID"
              description="Allow corporate sign-in with Microsoft Entra ID (formerly Azure Active Directory) or Microsoft 365 accounts."
              icon={
                <Box color="blue.600">
                  <FaMicrosoft />
                </Box>
              }
              fields={microsoftFields}
              setupNotes={[
                "Open Microsoft Entra Admin Center → App registrations → New registration.",
                "Select Web platform and paste the Authorized Redirect URI above.",
                "Under Certificates & secrets, create a New client secret and paste its Value (not Secret ID) above.",
              ]}
            />
          )}

          {selectedProvider === "ldap" && <LdapAuthProviderCard />}

          {selectedProvider === "passkey" && (
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
                      color="purple.500"
                      flexShrink={0}
                      mt={0.5}
                    >
                      <LuFingerprint />
                    </Flex>
                    <Box>
                      <HStack gap={2.5} wrap="wrap">
                        <Heading size="md">Passkeys (WebAuthn)</Heading>
                        <Badge
                          size="sm"
                          variant="subtle"
                          colorPalette={passkeyData?.enabled ? "green" : "gray"}
                        >
                          {passkeyData?.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </HStack>
                      <Text fontSize="sm" color="fg.muted" mt={1}>
                        Phishing-resistant passwordless authentication using
                        FIDO2 security keys (YubiKey), Touch ID, Face ID, or
                        Windows Hello.
                      </Text>
                    </Box>
                  </HStack>

                  {!passkeyLoading && (
                    <HStack
                      gap={3}
                      px={3}
                      py={2}
                      borderRadius="lg"
                      bg="bg.subtle"
                      borderWidth="1px"
                      alignSelf={{ base: "flex-start", sm: "center" }}
                      flexShrink={0}
                    >
                      <Text fontSize="xs" fontWeight="medium" color="fg.muted">
                        {passkeyData?.enabled ? "Active on login" : "Inactive"}
                      </Text>
                      <Switch.Root
                        colorPalette="teal"
                        checked={!!passkeyData?.enabled}
                        disabled={togglePasskeyMutation.isPending}
                        onCheckedChange={(e) =>
                          togglePasskeyMutation.mutate(e.checked)
                        }
                      >
                        <Switch.HiddenInput aria-label="Toggle Passkeys (WebAuthn)" />
                        <Switch.Control />
                      </Switch.Root>
                    </HStack>
                  )}
                </Flex>
              </Card.Header>

              <Separator />

              <Card.Body pt={5}>
                <VStack align="stretch" gap={5}>
                  <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
                    <Box
                      p={4}
                      borderRadius="lg"
                      borderWidth="1px"
                      bg="bg.subtle"
                    >
                      <HStack gap={2} mb={1.5} color="teal.600">
                        <LuUserCheck />
                        <Text fontSize="sm" fontWeight="semibold" color="fg">
                          User Self-Enrollment
                        </Text>
                      </HStack>
                      <Text fontSize="xs" color="fg.muted">
                        Once enabled, signed-in users can register one or more
                        passkeys under{" "}
                        <Text as="span" fontWeight="medium" color="fg">
                          User Settings → Passkeys
                        </Text>{" "}
                        and use them immediately via the &ldquo;Sign in with a
                        Passkey&rdquo; button on the login screen.
                      </Text>
                    </Box>

                    <Box
                      p={4}
                      borderRadius="lg"
                      borderWidth="1px"
                      bg="bg.subtle"
                    >
                      <HStack gap={2} mb={1.5} color="purple.500">
                        <LuLock />
                        <Text fontSize="sm" fontWeight="semibold" color="fg">
                          Origin & Relying Party
                        </Text>
                      </HStack>
                      <Text fontSize="xs" color="fg.muted">
                        WebAuthn credentials are bound automatically to this
                        site&apos;s domain (
                        <Text as="code" fontSize="xs">
                          {window.location.hostname}
                        </Text>
                        ). No external client ID or secret is required.
                      </Text>
                    </Box>
                  </SimpleGrid>

                  <Box p={4} borderRadius="lg" borderWidth="1px">
                    <Flex
                      justify="space-between"
                      align={{ base: "flex-start", sm: "center" }}
                      direction={{ base: "column", sm: "row" }}
                      gap={3}
                    >
                      <Box>
                        <HStack gap={2}>
                          <Text fontSize="sm" fontWeight="semibold">
                            Password Login Fallback
                          </Text>
                          <Badge
                            size="xs"
                            colorPalette={
                              localPasswordEnabled ? "green" : "yellow"
                            }
                            variant="subtle"
                          >
                            {localPasswordEnabled
                              ? "Passwords Allowed"
                              : "Passkey / SSO Only"}
                          </Badge>
                        </HStack>
                        <Text fontSize="xs" color="fg.muted" mt={1}>
                          {localPasswordEnabled
                            ? "Users can still sign in with their local email and password."
                            : "Local password login is disabled globally. Users must sign in with a Passkey, LDAP, or OAuth."}
                        </Text>
                      </Box>

                      <Button
                        size="xs"
                        variant="outline"
                        colorPalette={localPasswordEnabled ? "red" : "teal"}
                        loading={
                          disablePasswordMutation.isPending ||
                          enablePasswordMutation.isPending
                        }
                        onClick={() =>
                          localPasswordEnabled
                            ? disablePasswordMutation.mutate()
                            : enablePasswordMutation.mutate()
                        }
                      >
                        {localPasswordEnabled
                          ? "Enforce Passkey / SSO Only"
                          : "Re-enable Password Login"}
                      </Button>
                    </Flex>
                  </Box>
                </VStack>
              </Card.Body>
            </Card.Root>
          )}

          {selectedProvider === "password" && (
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
                      color="orange.500"
                      flexShrink={0}
                      mt={0.5}
                    >
                      <LuKeyRound />
                    </Flex>
                    <Box>
                      <HStack gap={2.5} wrap="wrap">
                        <Heading size="md">Local Password</Heading>
                        <Badge
                          size="sm"
                          variant="subtle"
                          colorPalette={localPasswordEnabled ? "green" : "gray"}
                        >
                          {localPasswordEnabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </HStack>
                      <Text fontSize="sm" color="fg.muted" mt={1}>
                        Built-in email and password authentication stored in the
                        local TACACS-NG UI database.
                      </Text>
                    </Box>
                  </HStack>

                  {!passkeyLoading && (
                    <HStack
                      gap={3}
                      px={3}
                      py={2}
                      borderRadius="lg"
                      bg="bg.subtle"
                      borderWidth="1px"
                      alignSelf={{ base: "flex-start", sm: "center" }}
                      flexShrink={0}
                    >
                      <Text fontSize="xs" fontWeight="medium" color="fg.muted">
                        {localPasswordEnabled ? "Active on login" : "Inactive"}
                      </Text>
                      <Switch.Root
                        colorPalette="teal"
                        checked={localPasswordEnabled}
                        disabled={
                          disablePasswordMutation.isPending ||
                          enablePasswordMutation.isPending
                        }
                        onCheckedChange={(e) =>
                          e.checked
                            ? enablePasswordMutation.mutate()
                            : disablePasswordMutation.mutate()
                        }
                      >
                        <Switch.HiddenInput aria-label="Toggle Local Password Login" />
                        <Switch.Control />
                      </Switch.Root>
                    </HStack>
                  )}
                </Flex>
              </Card.Header>

              <Separator />

              <Card.Body pt={5}>
                <VStack align="stretch" gap={4}>
                  {passwordLoginDisabled ? (
                    <Alert.Root status="warning" borderRadius="lg">
                      <Alert.Indicator />
                      <Alert.Content>
                        <Alert.Title>
                          Local password login is disabled
                        </Alert.Title>
                        <Alert.Description>
                          The email &amp; password sign-in form is hidden on the
                          login page. Users must authenticate with a Passkey,
                          LDAP directory account, or an enabled OAuth / OIDC
                          provider.
                        </Alert.Description>
                      </Alert.Content>
                      <Button
                        size="sm"
                        colorPalette="yellow"
                        ml="auto"
                        flexShrink={0}
                        loading={enablePasswordMutation.isPending}
                        onClick={() => enablePasswordMutation.mutate()}
                      >
                        Re-enable Passwords
                      </Button>
                    </Alert.Root>
                  ) : (
                    <Alert.Root status="info" borderRadius="lg">
                      <Alert.Indicator />
                      <Alert.Content>
                        <Alert.Title>
                          Local password login is active
                        </Alert.Title>
                        <Alert.Description>
                          Users with a local account can sign in using their
                          email address and password. You can also disable
                          password login per-user in{" "}
                          <Text as="span" fontWeight="semibold">
                            Admin → Users Management
                          </Text>
                          .
                        </Alert.Description>
                      </Alert.Content>
                    </Alert.Root>
                  )}

                  <Box
                    p={4}
                    borderRadius="lg"
                    bg="bg.subtle"
                    borderWidth="1px"
                    fontSize="xs"
                    color="fg.muted"
                  >
                    <Text fontWeight="semibold" color="fg" mb={2}>
                      Before Disabling Local Passwords
                    </Text>
                    <VStack align="stretch" gap={1.5}>
                      <HStack align="flex-start" gap={2}>
                        <Box color="teal.500" mt={0.5}>
                          <LuCheck />
                        </Box>
                        <Text>
                          Ensure at least one Superuser has registered a Passkey
                          or linked an active SSO/LDAP account so you do not
                          lose administrative access.
                        </Text>
                      </HStack>
                      <HStack align="flex-start" gap={2}>
                        <Box color="teal.500" mt={0.5}>
                          <LuCheck />
                        </Box>
                        <Text>
                          Disabling local passwords here automatically enables
                          Passkeys (WebAuthn) so passwordless sign-in remains
                          available.
                        </Text>
                      </HStack>
                    </VStack>
                  </Box>
                </VStack>
              </Card.Body>
            </Card.Root>
          )}
        </Box>
      </Grid>

      <DialogRoot
        size={{ base: "xs", md: "md" }}
        placement="center"
        open={passkeyDialogOpen}
        onOpenChange={({ open }) => setPasskeyDialogOpen(open)}
      >
        <DialogContent>
          <DialogCloseTrigger />
          <DialogHeader>
            <DialogTitle>Passkeys Enabled</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={3}>
              Passkeys (WebAuthn) are now enabled. Users can register a passkey
              in their account settings and use it to sign in.
            </Text>
            <Text color="fg.muted">
              You can optionally disable password-based login to enforce
              passkey-only authentication for all users.
            </Text>
          </DialogBody>
          <DialogFooter>
            <HStack gap={3}>
              <Button
                variant="outline"
                onClick={() => setPasskeyDialogOpen(false)}
              >
                Keep Password Login
              </Button>
              <Button
                colorPalette="red"
                loading={disablePasswordMutation.isPending}
                onClick={() => disablePasswordMutation.mutate()}
              >
                Disable Password Login
              </Button>
            </HStack>
          </DialogFooter>
        </DialogContent>
      </DialogRoot>
    </Container>
  )
}
