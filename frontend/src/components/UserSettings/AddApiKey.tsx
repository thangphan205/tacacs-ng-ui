import {
  Badge,
  Box,
  Button,
  Clipboard,
  Code,
  DialogTitle,
  HStack,
  IconButton,
  Input,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FiAlertTriangle, FiCheck, FiCopy, FiPlus } from "react-icons/fi"

import { type ApiKeyCreated, ApiKeysService } from "@/client"
import type { ApiError } from "@/client/core/ApiError"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { Checkbox } from "../ui/checkbox"
import {
  DialogActionTrigger,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTrigger,
} from "../ui/dialog"
import { Field } from "../ui/field"
import { Radio, RadioGroup } from "../ui/radio"
import McpClientGuide from "./McpClientGuide"

interface AccessLevel {
  value: string
  label: string
  description: string
}

const ACCESS_LEVELS: AccessLevel[] = [
  {
    value: "mcp:read",
    label: "Read-only",
    description:
      "Inspect TACACS+ entities and settings, render config previews and diffs, and syntax-check config. Changes nothing.",
  },
  {
    value: "mcp:write",
    label: "Read-write",
    description:
      "Everything in Read-only, plus creating, updating and deleting TACACS+ entities. Only works for superuser keys.",
  },
]

const SECRETS_SCOPE = "mcp:secrets"

const DEFAULT_ACCESS = "mcp:read"

interface FormValues {
  name: string
  description: string
  expires_in_days: number
  allowed_ips: string
}

const AddApiKey = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [access, setAccess] = useState<string>(DEFAULT_ACCESS)
  const [allowSecrets, setAllowSecrets] = useState(false)
  const [created, setCreated] = useState<ApiKeyCreated | null>(null)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()

  const scopes = allowSecrets ? [access, SECRETS_SCOPE] : [access]

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "",
      description: "",
      expires_in_days: 90,
      allowed_ips: "",
    },
  })

  const closeAll = () => {
    setIsOpen(false)
    setCreated(null)
    setAccess(DEFAULT_ACCESS)
    setAllowSecrets(false)
    reset()
  }

  const mutation = useMutation({
    mutationFn: (data: FormValues) =>
      ApiKeysService.createApiKey({
        requestBody: {
          name: data.name,
          description: data.description || null,
          scopes: scopes.join(","),
          expires_in_days: Number(data.expires_in_days),
          allowed_ips:
            data.allowed_ips
              .split("\n")
              .map((s) => s.trim())
              .filter(Boolean)
              .join(",") || null,
        },
      }),
    onSuccess: (data) => {
      showSuccessToast("API key created. Copy it now — it is shown only once.")
      setCreated(data)
    },
    onError: (err: ApiError) => handleError(err),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    },
  })

  const onSubmit: SubmitHandler<FormValues> = (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size={{ base: "xs", md: "lg", lg: "xl" }}
      placement="center"
      scrollBehavior="inside"
      open={isOpen}
      onOpenChange={({ open }) => (open ? setIsOpen(true) : closeAll())}
    >
      <DialogTrigger asChild>
        <Button size="sm" variant="solid">
          <FiPlus fontSize="16px" />
          Create API Key
        </Button>
      </DialogTrigger>

      <DialogContent maxH="85vh">
        {created ? (
          <>
            <DialogCloseTrigger />
            <DialogHeader>
              <DialogTitle>Copy your API key</DialogTitle>
            </DialogHeader>
            <DialogBody>
              <VStack align="stretch" gap={4}>
                <HStack
                  align="start"
                  gap={2}
                  p={3}
                  borderRadius="md"
                  borderWidth="1px"
                  borderColor="orange.400"
                >
                  <Box color="orange.500" pt={0.5}>
                    <FiAlertTriangle />
                  </Box>
                  <Text fontSize="sm">
                    This is the only time the key is shown. It is stored as a
                    one-way digest and cannot be recovered — if you lose it,
                    revoke this key and create another.
                  </Text>
                </HStack>

                <Field label="API key">
                  <HStack w="full">
                    <Code
                      flex="1"
                      p={2}
                      borderRadius="md"
                      wordBreak="break-all"
                      whiteSpace="pre-wrap"
                    >
                      {created.plaintext_key}
                    </Code>
                    <Clipboard.Root value={created.plaintext_key}>
                      <Clipboard.Trigger asChild>
                        <IconButton
                          variant="subtle"
                          size="sm"
                          aria-label="Copy API key"
                        >
                          <Clipboard.Indicator
                            copied={<FiCheck color="green" />}
                          >
                            <FiCopy />
                          </Clipboard.Indicator>
                        </IconButton>
                      </Clipboard.Trigger>
                    </Clipboard.Root>
                  </HStack>
                </Field>

                <HStack gap={4} wrap="wrap" justify="space-between">
                  <Box>
                    <Text fontSize="xs" color="gray.500" mb={1}>
                      Scopes
                    </Text>
                    <HStack gap={1} wrap="wrap">
                      {created.scopes
                        ?.split(",")
                        .filter(Boolean)
                        .map((scope) => (
                          <Badge
                            key={scope}
                            colorPalette={
                              scope === "mcp:secrets" || scope === "mcp:write"
                                ? "orange"
                                : "blue"
                            }
                            variant="subtle"
                            size="sm"
                          >
                            {scope}
                          </Badge>
                        ))}
                    </HStack>
                  </Box>

                  <Box>
                    <Text fontSize="xs" color="gray.500" mb={1}>
                      Allowed source IPs
                    </Text>
                    <Text fontSize="xs" fontFamily="mono">
                      {created.allowed_ips || "Any"}
                    </Text>
                  </Box>
                </HStack>

                <Box pt={1}>
                  <Text fontSize="sm" fontWeight="semibold" mb={2}>
                    Connect an MCP client
                  </Text>
                  <McpClientGuide apiKey={created.plaintext_key} />
                </Box>
              </VStack>
            </DialogBody>
            <DialogFooter gap={2}>
              <Button variant="solid" onClick={closeAll}>
                Done
              </Button>
            </DialogFooter>
          </>
        ) : (
          <form
            onSubmit={handleSubmit(onSubmit)}
            noValidate
            style={{
              display: "flex",
              flexDirection: "column",
              maxHeight: "85vh",
              overflow: "hidden",
              width: "100%",
              flex: 1,
            }}
          >
            <DialogCloseTrigger />
            <DialogHeader flexShrink={0}>
              <DialogTitle>Create API Key</DialogTitle>
            </DialogHeader>
            <DialogBody overflowY="auto" flex="1">
              <Text mb={4} fontSize="sm" color="gray.500">
                Machine credential for the MCP server. It cannot log in to this
                UI, and no MCP key can generate or activate a TACACS+ config —
                that stays a manual step you take on the TACACS Configs page.
              </Text>

              <VStack align="stretch" gap={4}>
                <Field
                  required
                  invalid={!!errors.name}
                  errorText={errors.name?.message}
                  label="Name"
                  helperText="How you will recognise this key in the list."
                >
                  <Input
                    {...register("name", {
                      required: "Name is required.",
                      maxLength: {
                        value: 255,
                        message: "Name must be 255 characters or fewer.",
                      },
                    })}
                    placeholder="claude-desktop-laptop"
                    type="text"
                  />
                </Field>

                <Field
                  invalid={!!errors.description}
                  errorText={errors.description?.message}
                  label="Description"
                  helperText="Optional."
                >
                  <Textarea
                    {...register("description", {
                      maxLength: {
                        value: 1024,
                        message:
                          "Description must be 1024 characters or fewer.",
                      },
                    })}
                    placeholder="What this key is for, who holds it"
                    rows={2}
                  />
                </Field>

                <Box>
                  <Text fontSize="sm" fontWeight="medium" mb={1}>
                    Access level
                  </Text>
                  <RadioGroup
                    value={access}
                    onValueChange={(e) => setAccess(e.value ?? DEFAULT_ACCESS)}
                  >
                    <VStack align="stretch" gap={3} pt={1}>
                      {ACCESS_LEVELS.map((level) => (
                        <Box key={level.value}>
                          <Radio value={level.value}>
                            <HStack gap={2}>
                              <Text fontSize="sm">{level.label}</Text>
                              <Text
                                fontFamily="mono"
                                fontSize="xs"
                                color="gray.500"
                              >
                                {level.value}
                              </Text>
                            </HStack>
                          </Radio>
                          <Text fontSize="xs" color="gray.500" ml={6}>
                            {level.description}
                          </Text>
                        </Box>
                      ))}
                    </VStack>
                  </RadioGroup>

                  {access === "mcp:write" && (
                    <HStack
                      align="start"
                      gap={2}
                      mt={3}
                      p={3}
                      borderRadius="md"
                      borderWidth="1px"
                      borderColor="orange.400"
                    >
                      <Box color="orange.500" pt={0.5}>
                        <FiAlertTriangle />
                      </Box>
                      <Text fontSize="sm">
                        An MCP client using this key can create, update and
                        delete TACACS+ users, groups, profiles, services, hosts,
                        rulesets and MAVIS entries. It still cannot deploy: the
                        changes sit in the database until <strong>you</strong>{" "}
                        open the TACACS Configs page and press Generate, then
                        Activate. Nothing reaches the running tac_plus-ng daemon
                        before that.
                      </Text>
                    </HStack>
                  )}

                  <Box mt={4}>
                    <Checkbox
                      checked={allowSecrets}
                      onCheckedChange={(e) => setAllowSecrets(!!e.checked)}
                    >
                      <HStack gap={2}>
                        <Text fontSize="sm">Allow unredacted secrets</Text>
                        <Badge colorPalette="orange" variant="subtle">
                          sensitive
                        </Badge>
                      </HStack>
                    </Checkbox>
                    <Text fontSize="xs" color="gray.500" ml={6}>
                      Adds <Code fontSize="xs">mcp:secrets</Code>: config can be
                      returned with device keys and passwords unmasked. Only
                      works for superuser keys, and every use is audit-logged.
                    </Text>
                  </Box>
                </Box>

                <Field
                  invalid={!!errors.allowed_ips}
                  errorText={errors.allowed_ips?.message}
                  label="Allowed source IPs"
                  helperText="Optional. One IPv4/IPv6 address or CIDR per line. Leave blank to allow any source. Editable later."
                >
                  <Textarea
                    {...register("allowed_ips")}
                    placeholder={"203.0.113.4\n198.51.100.0/24\n2001:db8::/32"}
                    rows={2}
                  />
                </Field>

                <Field
                  invalid={!!errors.expires_in_days}
                  errorText={errors.expires_in_days?.message}
                  label="Expires in (days)"
                  helperText="Use 0 for a key that never expires."
                >
                  <Input
                    {...register("expires_in_days", {
                      valueAsNumber: true,
                      min: { value: 0, message: "Must be 0 or more." },
                      max: {
                        value: 3650,
                        message: "Must be 3650 days or fewer.",
                      },
                    })}
                    type="number"
                    min={0}
                    max={3650}
                  />
                </Field>
              </VStack>
            </DialogBody>

            <DialogFooter gap={2} flexShrink={0}>
              <DialogActionTrigger asChild>
                <Button
                  variant="subtle"
                  colorPalette="gray"
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
              </DialogActionTrigger>
              <Button variant="solid" type="submit" loading={isSubmitting}>
                Create
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </DialogRoot>
  )
}

export default AddApiKey
