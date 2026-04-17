import { Container, Heading, SimpleGrid, Text } from "@chakra-ui/react"
import { createFileRoute, redirect } from "@tanstack/react-router"

import AuthProviderCard from "@/components/Admin/AuthProviderCard"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/admin/auth-providers")({
  component: AuthProvidersPage,
  beforeLoad: async ({ context }: { context: { queryClient: unknown } }) => {
    void context
  },
})

const googleFields = [
  { key: "client_id", label: "Client ID" },
  { key: "redirect_uri", label: "Redirect URI", placeholder: "https://api.example.com/api/v1/oauth/google/callback" },
]

const keycloakFields = [
  { key: "server_url", label: "Server URL", placeholder: "http://localhost:8080" },
  { key: "realm", label: "Realm", placeholder: "tacacs" },
  { key: "client_id", label: "Client ID" },
  { key: "redirect_uri", label: "Redirect URI", placeholder: "https://api.example.com/api/v1/oauth/keycloak/callback" },
]

function AuthProvidersPage() {
  const { user: currentUser } = useAuth()

  if (!currentUser?.is_superuser) {
    return <Text p={8}>Access denied.</Text>
  }

  return (
    <Container maxW="full">
      <Heading size="lg" py={8}>
        Authentication Providers
      </Heading>
      <SimpleGrid columns={{ base: 1, md: 3 }} gap={6}>
        <AuthProviderCard
          provider="google"
          title="Google OAuth"
          fields={googleFields}
        />
        <AuthProviderCard
          provider="keycloak"
          title="Keycloak OIDC"
          fields={keycloakFields}
        />
        <AuthProviderCard
          provider="passkey"
          title="Passkeys (WebAuthn)"
          fields={[]}
        />
      </SimpleGrid>
    </Container>
  )
}
