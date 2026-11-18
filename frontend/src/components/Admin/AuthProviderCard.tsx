import {
  Badge,
  Box,
  Button,
  Card,
  Flex,
  Heading,
  HStack,
  IconButton,
  Input,
  Separator,
  Switch,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Fragment, type ReactNode, useEffect, useState } from "react"
import {
  LuCheck,
  LuCopy,
  LuEye,
  LuEyeOff,
  LuKeyRound,
  LuRotateCcw,
  LuSave,
} from "react-icons/lu"

import { apiBaseUrl } from "@/api"
import { Tooltip } from "@/components/ui/tooltip"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export interface ProviderConfig {
  provider: string
  enabled: boolean
  config: Record<string, string>
  secret_is_set: boolean
}

export interface FieldDef {
  key: string
  label: string
  placeholder?: string
  hint?: string
  /** Prefilled when nothing is stored yet; saved with the form. */
  defaultValue?: string
  /** Show a one-click copy button next to the input (useful for Redirect URIs). */
  copyable?: boolean
  /** Render in monospace font (e.g., URIs, IDs). */
  mono?: boolean
}

interface AuthProviderCardProps {
  provider: string
  title: string
  description?: string
  icon?: ReactNode
  fields: FieldDef[]
  /** Render the client secret right after this field; default is after the last one. */
  secretAfter?: string
  secretLabel?: string
  setupNotes?: string[]
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
  description,
  icon,
  fields,
  secretAfter,
  secretLabel = "Client Secret",
  setupNotes,
  onEnabled,
}: AuthProviderCardProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data, isLoading } = useQuery({
    queryKey: ["auth-provider", provider],
    queryFn: () => fetchProvider(provider),
  })

  const [formConfig, setFormConfig] = useState<Record<string, string>>({})
  const [initialConfig, setInitialConfig] = useState<Record<string, string>>({})
  const [secret, setSecret] = useState("")
  const [showSecret, setShowSecret] = useState(false)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [initialized, setInitialized] = useState(false)

  useEffect(() => {
    if (data && !initialized) {
      const defaults = Object.fromEntries(
        fields
          .filter((f) => f.defaultValue)
          .map((f) => [f.key, f.defaultValue as string]),
      )
      const merged = { ...defaults, ...(data.config ?? {}) }
      setFormConfig(merged)
      setInitialConfig(merged)
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
    onSuccess: (updated) => {
      showSuccessToast(`${title} configuration saved.`)
      setSecret("")
      setShowSecret(false)
      const defaults = Object.fromEntries(
        fields
          .filter((f) => f.defaultValue)
          .map((f) => [f.key, f.defaultValue as string]),
      )
      const merged = { ...defaults, ...(updated.config ?? {}) }
      setFormConfig(merged)
      setInitialConfig(merged)
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

  const handleCopy = async (key: string, value: string) => {
    if (!value) return
    // navigator.clipboard exists only in a secure context (HTTPS or
    // localhost); the UI is often reached over plain HTTP on a LAN address.
    if (!navigator.clipboard) {
      showErrorToast(
        "Copying needs HTTPS. Select the text and copy it instead.",
      )
      return
    }
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      showErrorToast("Could not copy. Select the text and copy it instead.")
      return
    }
    setCopiedKey(key)
    setTimeout(() => {
      setCopiedKey((prev) => (prev === key ? null : prev))
    }, 2000)
  }

  const handleReset = () => {
    setFormConfig(initialConfig)
    setSecret("")
    setShowSecret(false)
  }

  const isDirty =
    secret.trim().length > 0 ||
    fields.some(
      (f) => (formConfig[f.key] ?? "") !== (initialConfig[f.key] ?? ""),
    )

  const secretField = (
    <Box>
      <HStack justify="space-between" mb={1.5}>
        <HStack gap={2}>
          <Text fontSize="sm" fontWeight="medium">
            {secretLabel}
          </Text>
          {data?.secret_is_set ? (
            <Badge size="xs" colorPalette="green" variant="subtle">
              <LuKeyRound />
              Configured
            </Badge>
          ) : (
            <Badge size="xs" colorPalette="orange" variant="subtle">
              Not set
            </Badge>
          )}
        </HStack>
      </HStack>
      <HStack gap={2}>
        <Input
          size="md"
          type={showSecret ? "text" : "password"}
          autoComplete="new-password"
          placeholder={
            data?.secret_is_set
              ? "•••••••••••••••• (leave blank to keep existing)"
              : `Enter ${secretLabel.toLowerCase()}`
          }
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
        />
        <Tooltip content={showSecret ? "Hide secret" : "Reveal secret"}>
          <IconButton
            aria-label={showSecret ? "Hide secret" : "Reveal secret"}
            variant="outline"
            size="md"
            onClick={() => setShowSecret((v) => !v)}
          >
            {showSecret ? <LuEyeOff /> : <LuEye />}
          </IconButton>
        </Tooltip>
      </HStack>
      <Text fontSize="xs" mt={1.5} color="fg.muted">
        Stored encrypted in the database and never sent back to the browser.
      </Text>
    </Box>
  )

  const secretKey = secretAfter ?? fields[fields.length - 1]?.key

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
            {icon && (
              <Flex
                w={10}
                h={10}
                borderRadius="lg"
                bg="bg.muted"
                borderWidth="1px"
                align="center"
                justify="center"
                fontSize="xl"
                flexShrink={0}
                mt={0.5}
              >
                {icon}
              </Flex>
            )}
            <Box>
              <HStack gap={2.5} wrap="wrap">
                <Heading size="md">{title}</Heading>
                <Badge
                  size="sm"
                  variant="subtle"
                  colorPalette={data?.enabled ? "green" : "gray"}
                >
                  {data?.enabled ? "Enabled" : "Disabled"}
                </Badge>
              </HStack>
              {description && (
                <Text fontSize="sm" color="fg.muted" mt={1}>
                  {description}
                </Text>
              )}
            </Box>
          </HStack>

          {!isLoading && (
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
                {data?.enabled ? "Active on login" : "Inactive"}
              </Text>
              <Switch.Root
                colorPalette="teal"
                checked={!!data?.enabled}
                disabled={toggleMutation.isPending}
                onCheckedChange={(e) => toggleMutation.mutate(e.checked)}
              >
                <Switch.HiddenInput aria-label={`Toggle ${title}`} />
                <Switch.Control />
              </Switch.Root>
            </HStack>
          )}
        </Flex>
      </Card.Header>

      <Separator />

      <Card.Body pt={5}>
        <VStack align="stretch" gap={5}>
          {fields.map((field) => {
            const val = formConfig[field.key] ?? ""
            const isCopied = copiedKey === field.key
            return (
              <Fragment key={field.key}>
                <Box>
                  <Text fontSize="sm" mb={1.5} fontWeight="medium">
                    {field.label}
                  </Text>
                  <HStack gap={2}>
                    <Input
                      size="md"
                      fontFamily={field.mono ? "mono" : undefined}
                      fontSize={field.mono ? "xs" : undefined}
                      placeholder={field.placeholder ?? field.label}
                      value={val}
                      onChange={(e) =>
                        setFormConfig((prev) => ({
                          ...prev,
                          [field.key]: e.target.value,
                        }))
                      }
                    />
                    {field.copyable && (
                      <Tooltip
                        content={isCopied ? "Copied!" : "Copy to clipboard"}
                      >
                        <IconButton
                          aria-label={`Copy ${field.label}`}
                          variant="outline"
                          size="md"
                          colorPalette={isCopied ? "green" : "gray"}
                          onClick={() => handleCopy(field.key, val)}
                        >
                          {isCopied ? <LuCheck /> : <LuCopy />}
                        </IconButton>
                      </Tooltip>
                    )}
                  </HStack>
                  {field.hint && (
                    <Text fontSize="xs" mt={1.5} color="fg.muted">
                      {field.hint}
                    </Text>
                  )}
                </Box>
                {field.key === secretKey && secretField}
              </Fragment>
            )
          })}

          {setupNotes && setupNotes.length > 0 && (
            <Box
              p={3.5}
              borderRadius="md"
              bg="bg.subtle"
              borderWidth="1px"
              fontSize="xs"
              color="fg.muted"
            >
              <Text fontWeight="semibold" color="fg" mb={1.5}>
                Quick Setup Checklist
              </Text>
              <VStack align="stretch" gap={1}>
                {setupNotes.map((note, idx) => (
                  <Text key={idx}>
                    {idx + 1}. {note}
                  </Text>
                ))}
              </VStack>
            </Box>
          )}

          {!isLoading && fields.length > 0 && (
            <>
              <Separator />
              <Flex justify="space-between" align="center" wrap="wrap" gap={3}>
                <Text fontSize="xs" color="fg.muted">
                  {isDirty
                    ? "You have unsaved configuration changes."
                    : "All configuration changes are saved."}
                </Text>
                <HStack gap={2.5}>
                  {isDirty && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleReset}
                      disabled={saveMutation.isPending}
                    >
                      <LuRotateCcw />
                      Discard
                    </Button>
                  )}
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
                </HStack>
              </Flex>
            </>
          )}
        </VStack>
      </Card.Body>
    </Card.Root>
  )
}

export default AuthProviderCard
