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
import { Fragment, useEffect, useState } from "react"

import { apiBaseUrl } from "@/api"
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
  hint?: string
  /** Prefilled when nothing is stored yet; saved with the form. */
  defaultValue?: string
}

interface AuthProviderCardProps {
  provider: string
  title: string
  fields: FieldDef[]
  /** Render the client secret right after this field; default is after the last one. */
  secretAfter?: string
  onEnabled?: () => void
}

function adminHeader() {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("access_token")}`,
  }
}

async function fetchProvider(provider: string): Promise<ProviderConfig> {
  const res = await fetch(
    `${apiBaseUrl()}/api/v1/admin/auth-providers/${provider}`,
    { headers: adminHeader() },
  )
  if (!res.ok) throw new Error("Failed to fetch provider config")
  return res.json()
}

async function saveProvider(
  provider: string,
  payload: {
    enabled?: boolean
    config?: Record<string, string>
    secret?: string
  },
): Promise<ProviderConfig> {
  const res = await fetch(
    `${apiBaseUrl()}/api/v1/admin/auth-providers/${provider}`,
    { method: "PUT", headers: adminHeader(), body: JSON.stringify(payload) },
  )
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail ?? "Save failed")
  }
  return res.json()
}

const AuthProviderCard = ({
  provider,
  title,
  fields,
  secretAfter,
  onEnabled,
}: AuthProviderCardProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()

  const { data, isLoading } = useQuery({
    queryKey: ["auth-provider", provider],
    queryFn: () => fetchProvider(provider),
  })

  const [formConfig, setFormConfig] = useState<Record<string, string>>({})
  const [secret, setSecret] = useState("")
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    if (data && !initialized) {
      const defaults = Object.fromEntries(
        fields
          .filter((f) => f.defaultValue)
          .map((f) => [f.key, f.defaultValue as string]),
      )
      setFormConfig({ ...defaults, ...(data.config ?? {}) })
      setInitialized(true)
    }
  }, [data, initialized, fields])

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
      if (updated.enabled && onEnabled) onEnabled()
    },
    onError: (err: Error) => handleError(err as never),
  })

  const secretField = (
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
  )

  const secretKey = secretAfter ?? fields[fields.length - 1]?.key

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
            <Fragment key={field.key}>
              <Box>
                <Text fontSize="xs" mb={1} fontWeight="medium">
                  {field.label}
                </Text>
                <Input
                  size="sm"
                  placeholder={field.placeholder ?? field.label}
                  value={formConfig[field.key] ?? ""}
                  onChange={(e) =>
                    setFormConfig((prev) => ({
                      ...prev,
                      [field.key]: e.target.value,
                    }))
                  }
                />
                {field.hint && (
                  <Text fontSize="xs" mt={1} color="fg.muted">
                    {field.hint}
                  </Text>
                )}
              </Box>
              {field.key === secretKey && secretField}
            </Fragment>
          ))}

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
