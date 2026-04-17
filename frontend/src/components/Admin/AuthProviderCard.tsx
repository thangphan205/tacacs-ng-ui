import {
  Badge,
  Box,
  Button,
  Card,
  Heading,
  HStack,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { OpenAPI } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ProviderConfig {
  provider: string
  enabled: boolean
  config: Record<string, string>
  secret_is_set: boolean
}

interface FieldDef {
  key: string
  label: string
  placeholder?: string
}

interface AuthProviderCardProps {
  provider: string
  title: string
  fields: FieldDef[]
}

function adminHeader() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("access_token")}`,
  }
}

async function fetchProvider(provider: string): Promise<ProviderConfig> {
  const res = await fetch(
    `${OpenAPI.BASE}/api/v1/admin/auth-providers/${provider}`,
    { headers: adminHeader() },
  )
  if (!res.ok) throw new Error("Failed to fetch provider config")
  return res.json()
}

async function saveProvider(
  provider: string,
  payload: { enabled?: boolean; config?: Record<string, string>; secret?: string },
): Promise<ProviderConfig> {
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

const AuthProviderCard = ({ provider, title, fields }: AuthProviderCardProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()

  const { data, isLoading } = useQuery({
    queryKey: ["auth-provider", provider],
    queryFn: () => fetchProvider(provider),
  })

  const [formConfig, setFormConfig] = useState<Record<string, string>>({})
  const [secret, setSecret] = useState("")
  const [initialized, setInitialized] = useState(false)

  if (data && !initialized) {
    setFormConfig(data.config ?? {})
    setInitialized(true)
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      saveProvider(provider, {
        enabled: data?.enabled,
        config: formConfig,
        secret: secret || undefined,
      }),
    onSuccess: () => {
      showSuccessToast(`${title} configuration saved.`)
      setSecret("")
      queryClient.invalidateQueries({ queryKey: ["auth-provider", provider] })
      queryClient.invalidateQueries({ queryKey: ["auth-providers-status"] })
    },
    onError: (err: Error) => handleError(err as never),
  })

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => saveProvider(provider, { enabled }),
    onSuccess: (updated) => {
      showSuccessToast(`${title} ${updated.enabled ? "enabled" : "disabled"}.`)
      queryClient.invalidateQueries({ queryKey: ["auth-provider", provider] })
      queryClient.invalidateQueries({ queryKey: ["auth-providers-status"] })
    },
    onError: (err: Error) => handleError(err as never),
  })

  return (
    <Card.Root variant="outline" p={4}>
      <Card.Header pb={2}>
        <HStack justify="space-between">
          <Heading size="sm">{title}</Heading>
          <Badge colorPalette={data?.enabled ? "green" : "gray"}>
            {data?.enabled ? "Enabled" : "Disabled"}
          </Badge>
        </HStack>
      </Card.Header>
      <Card.Body>
        <VStack align="stretch" gap={3}>
          {fields.map((field) => (
            <Box key={field.key}>
              <Text fontSize="xs" mb={1} fontWeight="medium">
                {field.label}
              </Text>
              <Input
                size="sm"
                placeholder={field.placeholder ?? field.label}
                value={formConfig[field.key] ?? ""}
                onChange={(e) =>
                  setFormConfig((prev) => ({ ...prev, [field.key]: e.target.value }))
                }
              />
            </Box>
          ))}

          {fields.length > 0 && (
            <Box>
              <Text fontSize="xs" mb={1} fontWeight="medium">
                Client Secret{" "}
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
                  data?.secret_is_set ? "Leave blank to keep existing" : "Enter secret"
                }
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
              />
            </Box>
          )}

          {!isLoading && (
            <HStack justify="space-between" pt={2}>
              <Button
                size="sm"
                colorPalette={data?.enabled ? "red" : "green"}
                variant="outline"
                loading={toggleMutation.isPending}
                onClick={() => toggleMutation.mutate(!data?.enabled)}
              >
                {data?.enabled ? "Disable" : "Enable"}
              </Button>
              {fields.length > 0 && (
                <Button
                  size="sm"
                  variant="solid"
                  loading={saveMutation.isPending}
                  onClick={() => saveMutation.mutate()}
                >
                  Save
                </Button>
              )}
            </HStack>
          )}
        </VStack>
      </Card.Body>
    </Card.Root>
  )
}

export default AuthProviderCard
