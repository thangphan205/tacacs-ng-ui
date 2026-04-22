import {
  Alert,
  Badge,
  Button,
  Container,
  Heading,
  HStack,
  Tabs,
  Text,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"
import { LuFolder, LuSquareCheck, LuUser } from "react-icons/lu"

import { OpenAPI } from "@/client"
import AuthProviderCard from "@/components/Admin/AuthProviderCard"
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

const googleFields = [
  { key: "client_id", label: "Client ID" },
  {
    key: "redirect_uri",
    label: "Redirect URI",
    placeholder: "https://api.example.com/api/v1/oauth/google/callback",
  },
]

const keycloakFields = [
  {
    key: "server_url",
    label: "Server URL",
    placeholder: "http://localhost:8080",
  },
  { key: "realm", label: "Realm", placeholder: "tacacs" },
  { key: "client_id", label: "Client ID" },
  {
    key: "redirect_uri",
    label: "Redirect URI",
    placeholder: "https://api.example.com/api/v1/oauth/keycloak/callback",
  },
]

function adminHeader() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("access_token")}`,
  }
}

async function fetchProvider(provider: string) {
  const res = await fetch(
    `${OpenAPI.BASE}/api/v1/admin/auth-providers/${provider}`,
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
    `${OpenAPI.BASE}/api/v1/admin/auth-providers/${provider}`,
    { method: "PUT", headers: adminHeader(), body: JSON.stringify(payload) },
  )
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail ?? "Save failed")
  }
  return res.json()
}

function StatusBadge({ enabled }: { enabled?: boolean }) {
  if (enabled === undefined) return null
  return (
    <Badge size="sm" colorPalette={enabled ? "green" : "gray"} ml={1}>
      {enabled ? "On" : "Off"}
    </Badge>
  )
}

function AuthProvidersPage() {
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const [passkeyDialogOpen, setPasskeyDialogOpen] = useState(false)

  const { data: googleData } = useQuery({
    queryKey: ["auth-provider", "google"],
    queryFn: () => fetchProvider("google"),
  })
  const { data: keycloakData } = useQuery({
    queryKey: ["auth-provider", "keycloak"],
    queryFn: () => fetchProvider("keycloak"),
  })
  const { data: passkeyData } = useQuery({
    queryKey: ["auth-provider", "passkey"],
    queryFn: () => fetchProvider("passkey"),
  })

  const disablePasswordMutation = useMutation({
    mutationFn: () =>
      saveProvider("passkey", {
        enabled: true,
        config: { ...passkeyData?.config, allow_password_login: "false" },
      }),
    onSuccess: () => {
      showSuccessToast("Password login disabled. Users must use a passkey.")
      queryClient.invalidateQueries({ queryKey: ["auth-provider", "passkey"] })
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
      showSuccessToast("Password login re-enabled.")
      queryClient.invalidateQueries({ queryKey: ["auth-provider", "passkey"] })
    },
    onError: (err: Error) => handleError(err as never),
  })

  const passwordLoginDisabled =
    passkeyData?.config?.allow_password_login === "false"

  if (!currentUser?.is_superuser) {
    return <Text p={8}>Access denied.</Text>
  }

  return (
    <Container maxW="full">
      <Heading size="lg" py={8}>
        Authentication Providers
      </Heading>

      <Tabs.Root defaultValue="google">
        <Tabs.List>
          <Tabs.Trigger value="google">
            <LuUser />
            Google OAuth
            <StatusBadge enabled={googleData?.enabled} />
          </Tabs.Trigger>
          <Tabs.Trigger value="keycloak">
            <LuFolder />
            Keycloak OIDC
            <StatusBadge enabled={keycloakData?.enabled} />
          </Tabs.Trigger>
          <Tabs.Trigger value="passkey">
            <LuSquareCheck />
            Passkeys (WebAuthn)
            <StatusBadge enabled={passkeyData?.enabled} />
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="google">
          <AuthProviderCard
            provider="google"
            title="Google OAuth"
            fields={googleFields}
          />
        </Tabs.Content>
        <Tabs.Content value="keycloak">
          <AuthProviderCard
            provider="keycloak"
            title="Keycloak OIDC"
            fields={keycloakFields}
          />
        </Tabs.Content>
        <Tabs.Content value="passkey">
          <AuthProviderCard
            provider="passkey"
            title="Passkeys (WebAuthn)"
            fields={[]}
            onEnabled={() => setPasskeyDialogOpen(true)}
          />
          {passwordLoginDisabled && (
            <Alert.Root status="warning" mt={4} borderRadius="md">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title>Password login is disabled</Alert.Title>
                <Alert.Description>
                  Users can only sign in with a passkey. Re-enable to allow
                  password-based login again.
                </Alert.Description>
              </Alert.Content>
              <Button
                size="sm"
                colorPalette="yellow"
                ml="auto"
                loading={enablePasswordMutation.isPending}
                onClick={() => enablePasswordMutation.mutate()}
              >
                Re-enable Password Login
              </Button>
            </Alert.Root>
          )}
        </Tabs.Content>
      </Tabs.Root>

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
