import {
  Badge,
  Box,
  Collapsible,
  Flex,
  Grid,
  GridItem,
  HStack,
  IconButton,
  Input,
  SimpleGrid,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import type React from "react"
import { useMemo, useState } from "react"
import { Controller, type UseFormReturn } from "react-hook-form"
import {
  FiChevronDown,
  FiCode,
  FiEye,
  FiEyeOff,
  FiGlobe,
  FiHash,
  FiInfo,
  FiKey,
  FiLayers,
  FiMessageSquare,
  FiRadio,
  FiServer,
  FiSettings,
  FiShield,
  FiSliders,
  FiType,
} from "react-icons/fi"
import FieldGuide, { type FieldGuideItem } from "@/components/Common/FieldGuide"
import { configNameRule } from "@/utils"
import { Checkbox } from "../ui/checkbox"
import { Field } from "../ui/field"
import { InputGroup } from "../ui/input-group"
import { HostSelect } from "./HostSelect"
import { SAFE_KEY } from "./hostKeys"

export interface HostFormValues {
  name: string
  ipv4_address?: string
  ipv6_address?: string
  secret_key?: string
  radius_secret_key?: string
  description?: string
  welcome_banner?: string
  reject_banner?: string
  motd_banner?: string
  failed_authentication_banner?: string
  parent?: string
  generate_config?: boolean
}

const baseFieldGuideItems: FieldGuideItem[] = [
  {
    icon: FiType,
    label: "Name",
    description:
      "A unique identifier for this network device. Used in the generated TACACS+ config and as reference across the UI.",
    example: "core-switch-01, dc1-fw-primary",
    required: true,
  },
  {
    icon: FiGlobe,
    label: "IPv4 Address / CIDR",
    description:
      "The management IP address or subnet (CIDR) of the device. CIDR notation allows a range of devices to share the same TACACS+ key.",
    example: "10.0.1.1 or 10.0.1.0/24",
    required: true,
  },
  {
    icon: FiHash,
    label: "IPv6 Address",
    description:
      "Optional IPv6 management address. Set this if your device connects to the TACACS+ server over IPv6.",
    example: "2001:db8::1",
  },
  {
    icon: FiLayers,
    label: "Parent Host",
    description:
      "Optionally inherit from an existing host. The child is rendered with parent = <host> and inherits its key (and other settings) when it has none of its own.",
  },
  {
    icon: FiKey,
    label: "Secret Key",
    description:
      "The shared secret between this device and the TACACS+ server. Must match the key configured on the network device exactly (case-sensitive). Not needed for a RADIUS-only device.",
    example: "MyS3cretK3y!",
    required: true,
  },
  {
    icon: FiRadio,
    label: "RADIUS Secret",
    description:
      "Shared secret for RADIUS (only while RADIUS is enabled under TACACS NG Settings). The server answers RADIUS only for hosts with one, own or inherited from the parent. Use it for devices that speak only RADIUS, such as MikroTik.",
    example: "MyR4diusS3cret",
  },
  {
    icon: FiInfo,
    label: "Description",
    description:
      "Free-text note for your reference. Not included in the generated config — useful for documenting location, role, or owner.",
  },
  {
    icon: FiSettings,
    label: "Generate to Config",
    description:
      "When enabled, this host will be included in the generated TACACS+ daemon configuration file. Disable to keep the record without activating it.",
  },
  {
    icon: FiMessageSquare,
    label: "Banner Messages",
    description:
      "Optional banners displayed to users during authentication: Welcome (on success), Reject (on deny), MOTD (after login), and Failed Authentication.",
  },
]

interface SectionCardProps {
  icon: React.ElementType
  title: string
  badge?: React.ReactNode
  children: React.ReactNode
}

function SectionCard({ icon: Icon, title, badge, children }: SectionCardProps) {
  return (
    <Box
      p={4}
      borderRadius="xl"
      borderWidth="1px"
      borderColor="border.subtle"
      bg="bg.panel"
    >
      <Flex align="center" justify="space-between" mb={3.5} gap={2}>
        <HStack gap={2}>
          <Box
            p={1.5}
            borderRadius="md"
            bg="teal.muted"
            color="teal.fg"
            display="flex"
            alignItems="center"
            justifyContent="center"
          >
            <Icon size={13} />
          </Box>
          <Text
            fontSize="xs"
            fontWeight="bold"
            textTransform="uppercase"
            letterSpacing="wider"
            color="fg.muted"
          >
            {title}
          </Text>
        </HStack>
        {badge}
      </Flex>
      {children}
    </Box>
  )
}

interface HostConfigPreviewProps {
  name?: string
  ipv4?: string
  parent?: string
  hasSecretKey: boolean
  hasRadiusSecret: boolean
  radiusEnabled: boolean
  generateConfig: boolean
}

function HostConfigPreview({
  name,
  ipv4,
  parent,
  hasSecretKey,
  hasRadiusSecret,
  radiusEnabled,
  generateConfig,
}: HostConfigPreviewProps) {
  const displayName = name?.trim() || "core-switch-01"
  const displayIp = ipv4?.trim() || "192.168.1.1"
  const isPlaceholder = !name?.trim() && !ipv4?.trim()

  const lines: string[] = []
  if (parent) {
    lines.push(`    parent = ${parent}`)
  }
  lines.push(`    address = ${displayIp}`)
  if (hasSecretKey) {
    lines.push('    key = "••••••••"')
  } else if (parent) {
    lines.push(`    # key inherited from ${parent}`)
  } else if (radiusEnabled && hasRadiusSecret) {
    lines.push("    # key auto-generated (RADIUS-only)")
  } else {
    lines.push('    key = "<shared-secret>"')
  }
  if (radiusEnabled && hasRadiusSecret) {
    lines.push('    radius.key = "••••••••"')
  }

  const block = `host = ${displayName} {\n${lines.join("\n")}\n}`

  return (
    <Box
      borderRadius="xl"
      borderWidth="1px"
      borderColor="border.subtle"
      bg="bg.muted/60"
      overflow="hidden"
    >
      <Flex
        align="center"
        justify="space-between"
        px={4}
        py={2.5}
        borderBottomWidth="1px"
        borderColor="border.subtle"
        bg="bg.muted/80"
      >
        <HStack gap={2}>
          <Box color="teal.fg">
            <FiCode size={14} />
          </Box>
          <Text
            fontSize="xs"
            fontWeight="bold"
            textTransform="uppercase"
            letterSpacing="wider"
            color="teal.fg"
          >
            Config Preview
          </Text>
        </HStack>
        <Badge
          colorPalette={generateConfig ? "teal" : "gray"}
          variant="subtle"
          size="sm"
          fontSize="2xs"
        >
          {generateConfig ? "Included" : "Excluded"}
        </Badge>
      </Flex>
      <Box p={3.5} opacity={generateConfig ? 1 : 0.55}>
        <Box
          as="pre"
          fontFamily="mono"
          fontSize="xs"
          lineHeight="1.65"
          color={isPlaceholder ? "fg.muted" : "fg"}
          overflowX="auto"
          m={0}
          whiteSpace="pre"
        >
          {block}
        </Box>
        {!generateConfig && (
          <Text fontSize="2xs" color="fg.muted" mt={2}>
            Disabled — this host will be saved in the database but omitted from
            the TACACS+ daemon config.
          </Text>
        )}
      </Box>
    </Box>
  )
}

interface HostFormProps {
  form: UseFormReturn<HostFormValues>
  radiusEnabled: boolean
  showRadiusSecret: boolean
  howItWorks: string
  /** Existing host name when editing, so validation allows keeping the current name. */
  existingName?: string
  /** Host ID to exclude from the Parent Host selector when editing. */
  excludeHostId?: string
}

export function HostForm({
  form,
  radiusEnabled,
  showRadiusSecret,
  howItWorks,
  existingName,
  excludeHostId,
}: HostFormProps) {
  const {
    register,
    setValue,
    getValues,
    trigger,
    watch,
    control,
    formState: { errors },
  } = form

  const [activeGuide, setActiveGuide] = useState<string | null>(null)
  const [showSecretKey, setShowSecretKey] = useState(false)
  const [showRadiusKey, setShowRadiusKey] = useState(false)
  const [bannersOpen, setBannersOpen] = useState(false)

  const watchedName = watch("name")
  const watchedIpv4 = watch("ipv4_address")
  const watchedSecretKey = watch("secret_key")
  const watchedRadiusSecret = watch("radius_secret_key")
  const parentValue = watch("parent")
  const generateConfig = watch("generate_config") ?? true
  const welcomeBanner = watch("welcome_banner")
  const rejectBanner = watch("reject_banner")
  const motdBanner = watch("motd_banner")
  const failedBanner = watch("failed_authentication_banner")

  const configuredBannerCount = [
    welcomeBanner,
    rejectBanner,
    motdBanner,
    failedBanner,
  ].filter((v) => !!v?.trim()).length

  const guideItems = useMemo(
    () =>
      baseFieldGuideItems
        .filter((item) => showRadiusSecret || item.label !== "RADIUS Secret")
        .map((item) =>
          item.label === "Secret Key"
            ? { ...item, required: !showRadiusSecret && !parentValue }
            : item,
        ),
    [showRadiusSecret, parentValue],
  )

  return (
    <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
      {/* Left Column: Structured Form Sections */}
      <GridItem>
        <VStack gap={4} align="stretch" as="section">
          {/* Section 1: Identity & Network */}
          <SectionCard icon={FiServer} title="Identity & Network">
            <VStack gap={3.5} align="stretch">
              <Field
                required
                invalid={!!errors.name}
                errorText={errors.name?.message}
                label="Name"
              >
                <Input
                  {...register("name", {
                    required: "Name is required.",
                    validate: configNameRule("Host name", existingName),
                  })}
                  placeholder="core-switch-01"
                  type="text"
                  fontFamily="mono"
                  onFocus={() => setActiveGuide("Name")}
                />
              </Field>

              <SimpleGrid columns={{ base: 1, sm: 2 }} gap={3.5} w="full">
                <Field
                  required
                  invalid={!!errors.ipv4_address}
                  errorText={errors.ipv4_address?.message}
                  label="IPv4 Address / CIDR"
                >
                  <Input
                    {...register("ipv4_address", {
                      required: "IPv4 address is required.",
                    })}
                    placeholder="192.168.1.1 or 192.168.1.0/24"
                    type="text"
                    fontFamily="mono"
                    onFocus={() => setActiveGuide("IPv4 Address / CIDR")}
                  />
                </Field>

                <Field
                  invalid={!!errors.ipv6_address}
                  errorText={errors.ipv6_address?.message}
                  label="IPv6 Address"
                  optionalText={
                    <Text as="span" fontSize="xs" color="fg.muted" ml={1}>
                      (optional)
                    </Text>
                  }
                >
                  <Input
                    {...register("ipv6_address")}
                    placeholder="2001:db8::1"
                    type="text"
                    fontFamily="mono"
                    onFocus={() => setActiveGuide("IPv6 Address")}
                  />
                </Field>
              </SimpleGrid>

              <Field
                invalid={!!errors.description}
                errorText={errors.description?.message}
                label="Description"
                optionalText={
                  <Text as="span" fontSize="xs" color="fg.muted" ml={1}>
                    (optional)
                  </Text>
                }
              >
                <Input
                  {...register("description")}
                  placeholder="e.g. DC1 core distribution switch"
                  type="text"
                  onFocus={() => setActiveGuide("Description")}
                />
              </Field>
            </VStack>
          </SectionCard>

          {/* Section 2: Authentication & Inheritance */}
          <SectionCard
            icon={FiShield}
            title="Authentication & Inheritance"
            badge={
              parentValue ? (
                <Badge colorPalette="teal" variant="subtle" size="sm">
                  Inheriting from {parentValue}
                </Badge>
              ) : undefined
            }
          >
            <VStack gap={3.5} align="stretch">
              <Field
                invalid={!!errors.parent}
                errorText={errors.parent?.message}
                label="Parent Host"
                helperText="Optional. Child hosts inherit keys and settings from their parent when left blank."
              >
                <HostSelect
                  value={parentValue}
                  excludeId={excludeHostId}
                  onFocus={() => setActiveGuide("Parent Host")}
                  onChange={(name) => {
                    setValue("parent", name, { shouldDirty: true })
                    if (errors.secret_key) trigger("secret_key")
                  }}
                />
              </Field>

              <SimpleGrid
                columns={{ base: 1, sm: showRadiusSecret ? 2 : 1 }}
                gap={3.5}
                w="full"
              >
                <Field
                  required={!parentValue && !showRadiusSecret}
                  invalid={!!errors.secret_key}
                  errorText={errors.secret_key?.message}
                  label="Secret Key"
                  helperText={
                    showRadiusSecret
                      ? "TACACS+ shared secret (optional for RADIUS-only)."
                      : undefined
                  }
                >
                  <InputGroup
                    w="full"
                    endElement={
                      <IconButton
                        aria-label={
                          showSecretKey ? "Hide secret key" : "Show secret key"
                        }
                        variant="ghost"
                        size="xs"
                        tabIndex={-1}
                        color="fg.muted"
                        onClick={() => setShowSecretKey((prev) => !prev)}
                      >
                        {showSecretKey ? <FiEyeOff /> : <FiEye />}
                      </IconButton>
                    }
                  >
                    <Input
                      {...register("secret_key", {
                        pattern: SAFE_KEY,
                        validate: (value) =>
                          !!value ||
                          !!getValues("radius_secret_key") ||
                          !!getValues("parent") ||
                          (showRadiusSecret
                            ? "Set a secret key or a RADIUS secret, unless a parent host is set."
                            : "Secret key is required unless a parent host is set."),
                      })}
                      placeholder={
                        parentValue
                          ? "Inherited from parent if empty"
                          : "TACACS+ shared secret"
                      }
                      type={showSecretKey ? "text" : "password"}
                      fontFamily={showSecretKey ? "mono" : undefined}
                      onFocus={() => setActiveGuide("Secret Key")}
                    />
                  </InputGroup>
                </Field>

                {showRadiusSecret && (
                  <Field
                    invalid={!!errors.radius_secret_key}
                    errorText={errors.radius_secret_key?.message}
                    label="RADIUS Secret"
                    helperText={
                      radiusEnabled
                        ? "Optional. For RADIUS devices (e.g. MikroTik)."
                        : "RADIUS is disabled: secret is kept but not used."
                    }
                  >
                    <InputGroup
                      w="full"
                      endElement={
                        <IconButton
                          aria-label={
                            showRadiusKey
                              ? "Hide RADIUS secret"
                              : "Show RADIUS secret"
                          }
                          variant="ghost"
                          size="xs"
                          tabIndex={-1}
                          color="fg.muted"
                          onClick={() => setShowRadiusKey((prev) => !prev)}
                        >
                          {showRadiusKey ? <FiEyeOff /> : <FiEye />}
                        </IconButton>
                      }
                    >
                      <Input
                        {...register("radius_secret_key", {
                          pattern: SAFE_KEY,
                          deps: ["secret_key"],
                        })}
                        placeholder={
                          parentValue
                            ? "Inherited from parent if empty"
                            : "RADIUS shared secret"
                        }
                        type={showRadiusKey ? "text" : "password"}
                        fontFamily={showRadiusKey ? "mono" : undefined}
                        onFocus={() => setActiveGuide("RADIUS Secret")}
                      />
                    </InputGroup>
                  </Field>
                )}
              </SimpleGrid>
            </VStack>
          </SectionCard>

          {/* Section 3: Config & Banners */}
          <SectionCard icon={FiSliders} title="Config & Banners">
            <VStack gap={3} align="stretch">
              <Controller
                control={control}
                name="generate_config"
                render={({ field }) => (
                  <Box
                    p={3}
                    borderRadius="lg"
                    borderWidth="1px"
                    borderColor={field.value ? "teal.muted" : "border.subtle"}
                    bg={field.value ? "teal.subtle/20" : "bg.muted/30"}
                    transition="all 0.15s ease"
                    onClick={() => setActiveGuide("Generate to Config")}
                  >
                    <Flex align="center" justify="space-between" gap={3}>
                      <Field disabled={field.disabled} colorPalette="teal">
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={({ checked }) =>
                            field.onChange(checked)
                          }
                        >
                          <Box>
                            <Text fontSize="sm" fontWeight="medium" color="fg">
                              Generate to TACACS+ Config
                            </Text>
                            <Text fontSize="xs" color="fg.muted">
                              Include this host block in the generated daemon
                              configuration file.
                            </Text>
                          </Box>
                        </Checkbox>
                      </Field>
                      <Badge
                        colorPalette={field.value ? "teal" : "gray"}
                        variant="subtle"
                        size="sm"
                        flexShrink={0}
                      >
                        {field.value ? "Active" : "Inactive"}
                      </Badge>
                    </Flex>
                  </Box>
                )}
              />

              <Collapsible.Root
                open={bannersOpen}
                onOpenChange={({ open }) => {
                  setBannersOpen(open)
                  if (open) setActiveGuide("Banner Messages")
                }}
              >
                <Box
                  borderRadius="lg"
                  borderWidth="1px"
                  borderColor={bannersOpen ? "teal.muted" : "border.subtle"}
                  overflow="hidden"
                  transition="border-color 0.15s ease"
                >
                  <Collapsible.Trigger
                    w="full"
                    display="flex"
                    alignItems="center"
                    justifyContent="space-between"
                    px={3.5}
                    py={2.5}
                    bg={bannersOpen ? "bg.muted/50" : "transparent"}
                    _hover={{ bg: "bg.muted/60" }}
                    cursor="pointer"
                    transition="background 0.15s ease"
                  >
                    <HStack gap={2.5}>
                      <Box color="teal.fg">
                        <FiMessageSquare size={15} />
                      </Box>
                      <Text fontSize="sm" fontWeight="medium" color="fg">
                        Configure Banner Messages
                      </Text>
                      <Badge
                        colorPalette={
                          configuredBannerCount > 0 ? "teal" : "gray"
                        }
                        variant="subtle"
                        size="sm"
                        fontSize="2xs"
                      >
                        {configuredBannerCount > 0
                          ? `${configuredBannerCount} configured`
                          : "Optional"}
                      </Badge>
                    </HStack>
                    <Box
                      color="fg.muted"
                      transition="transform 0.2s ease"
                      transform={
                        bannersOpen ? "rotate(180deg)" : "rotate(0deg)"
                      }
                    >
                      <FiChevronDown size={16} />
                    </Box>
                  </Collapsible.Trigger>
                  <Collapsible.Content>
                    <Box
                      p={3.5}
                      borderTopWidth="1px"
                      borderColor="border.subtle"
                      bg="bg.muted/20"
                    >
                      <SimpleGrid columns={{ base: 1, md: 2 }} gap={3.5}>
                        <Field
                          invalid={!!errors.welcome_banner}
                          errorText={errors.welcome_banner?.message}
                          label="Welcome Banner"
                        >
                          <Textarea
                            {...register("welcome_banner")}
                            rows={2}
                            placeholder="Message shown on successful login"
                            onFocus={() => setActiveGuide("Banner Messages")}
                          />
                        </Field>
                        <Field
                          invalid={!!errors.reject_banner}
                          errorText={errors.reject_banner?.message}
                          label="Reject Banner"
                        >
                          <Textarea
                            {...register("reject_banner")}
                            rows={2}
                            placeholder="Message shown when access is denied"
                            onFocus={() => setActiveGuide("Banner Messages")}
                          />
                        </Field>
                        <Field
                          invalid={!!errors.motd_banner}
                          errorText={errors.motd_banner?.message}
                          label="MOTD Banner"
                        >
                          <Textarea
                            {...register("motd_banner")}
                            rows={2}
                            placeholder="Message of the day shown after login"
                            onFocus={() => setActiveGuide("Banner Messages")}
                          />
                        </Field>
                        <Field
                          invalid={!!errors.failed_authentication_banner}
                          errorText={
                            errors.failed_authentication_banner?.message
                          }
                          label="Failed Auth Banner"
                        >
                          <Textarea
                            {...register("failed_authentication_banner")}
                            rows={2}
                            placeholder="Message shown on failed authentication"
                            onFocus={() => setActiveGuide("Banner Messages")}
                          />
                        </Field>
                      </SimpleGrid>
                    </Box>
                  </Collapsible.Content>
                </Box>
              </Collapsible.Root>
            </VStack>
          </SectionCard>
        </VStack>
      </GridItem>

      {/* Right Column: Live Config Preview + Context-Aware Field Guide */}
      <GridItem>
        <VStack gap={4} align="stretch">
          <HostConfigPreview
            name={watchedName}
            ipv4={watchedIpv4}
            parent={parentValue}
            hasSecretKey={!!watchedSecretKey}
            hasRadiusSecret={!!watchedRadiusSecret}
            radiusEnabled={radiusEnabled}
            generateConfig={generateConfig}
          />
          <FieldGuide
            items={guideItems}
            icon={FiServer}
            subtitle="Focus any field on the left to inspect how it maps to the TACACS+ daemon config."
            howItWorks={howItWorks}
            activeLabel={activeGuide}
          />
        </VStack>
      </GridItem>
    </Grid>
  )
}
