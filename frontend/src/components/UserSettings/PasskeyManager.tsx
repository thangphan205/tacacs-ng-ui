import {
  Button,
  Container,
  Heading,
  HStack,
  Input,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { startRegistration } from "@simplewebauthn/browser"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { OpenAPI } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface PasskeyItem {
  id: string
  credential_id: string
  name: string | null
  created_at: string
  last_used_at: string | null
}

function authHeader() {
  return { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
}

async function fetchPasskeys(): Promise<{ data: PasskeyItem[]; count: number }> {
  const res = await fetch(`${OpenAPI.BASE}/api/v1/passkeys/`, {
    headers: authHeader(),
  })
  if (!res.ok) throw new Error("Failed to load passkeys")
  return res.json()
}

async function beginRegistration() {
  const res = await fetch(`${OpenAPI.BASE}/api/v1/passkeys/register/begin`, {
    method: "POST",
    headers: authHeader(),
  })
  if (!res.ok) throw new Error("Failed to begin registration")
  return res.json()
}

async function completeRegistration(credential: unknown, name: string | null) {
  const res = await fetch(`${OpenAPI.BASE}/api/v1/passkeys/register/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({ credential, name }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail ?? "Registration failed")
  }
  return res.json()
}

async function removePasskey(id: string) {
  const res = await fetch(`${OpenAPI.BASE}/api/v1/passkeys/${id}`, {
    method: "DELETE",
    headers: authHeader(),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail ?? "Delete failed")
  }
  return res.json()
}

const PasskeyManager = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const [passkeyName, setPasskeyName] = useState("")
  const [isRegistering, setIsRegistering] = useState(false)

  const { data } = useQuery({
    queryKey: ["passkeys"],
    queryFn: fetchPasskeys,
  })

  const registerMutation = useMutation({
    mutationFn: async () => {
      setIsRegistering(true)
      try {
        const options = await beginRegistration()
        const credential = await startRegistration({ optionsJSON: options })
        await completeRegistration(credential, passkeyName.trim() || null)
      } finally {
        setIsRegistering(false)
      }
    },
    onSuccess: () => {
      showSuccessToast("Passkey registered successfully.")
      setPasskeyName("")
      queryClient.invalidateQueries({ queryKey: ["passkeys"] })
    },
    onError: (err: Error) => {
      if (err.name === "NotAllowedError") return
      handleError(err as never)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => removePasskey(id),
    onSuccess: () => {
      showSuccessToast("Passkey removed.")
      queryClient.invalidateQueries({ queryKey: ["passkeys"] })
    },
    onError: (err: Error) => handleError(err as never),
  })

  const passkeys = data?.data ?? []

  return (
    <Container maxW="full">
      <Heading size="sm" py={4}>
        Security Keys (Passkeys)
      </Heading>

      {passkeys.length > 0 ? (
        <Table.Root mb={4} size="sm">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Name</Table.ColumnHeader>
              <Table.ColumnHeader>Added</Table.ColumnHeader>
              <Table.ColumnHeader>Last used</Table.ColumnHeader>
              <Table.ColumnHeader />
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {passkeys.map((pk) => (
              <Table.Row key={pk.id}>
                <Table.Cell>{pk.name ?? "Unnamed key"}</Table.Cell>
                <Table.Cell>
                  {new Date(pk.created_at).toLocaleDateString()}
                </Table.Cell>
                <Table.Cell>
                  {pk.last_used_at
                    ? new Date(pk.last_used_at).toLocaleDateString()
                    : "Never"}
                </Table.Cell>
                <Table.Cell>
                  <Button
                    size="xs"
                    colorPalette="red"
                    variant="ghost"
                    loading={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(pk.id)}
                  >
                    Remove
                  </Button>
                </Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      ) : (
        <Text color="gray.500" mb={4}>
          No passkeys registered yet.
        </Text>
      )}

      <VStack align="start" gap={3}>
        <Text fontSize="sm" fontWeight="medium">
          Register a new passkey
        </Text>
        <HStack>
          <Input
            placeholder="Key name (optional)"
            value={passkeyName}
            onChange={(e) => setPasskeyName(e.target.value)}
            maxW="xs"
            size="sm"
          />
          <Button
            size="sm"
            variant="solid"
            loading={isRegistering || registerMutation.isPending}
            onClick={() => registerMutation.mutate()}
          >
            Register Passkey
          </Button>
        </HStack>
      </VStack>
    </Container>
  )
}

export default PasskeyManager
