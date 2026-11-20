import {
  Button,
  ButtonGroup,
  Collapsible,
  DialogActionTrigger,
  Grid,
  GridItem,
  Input,
  SimpleGrid,
  Text,
  Textarea,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"
import {
  FiGlobe,
  FiHash,
  FiInfo,
  FiKey,
  FiLayers,
  FiMessageSquare,
  FiRadio,
  FiServer,
  FiSettings,
  FiType,
} from "react-icons/fi"
import type { ApiError } from "@/api"
import { type HostPublic, HostsService } from "@/client"
import { defaultCredentialsQueryKey } from "@/components/Common/DefaultCredentialsAlert"
import FieldGuide, { type FieldGuideItem } from "@/components/Common/FieldGuide"
import useCustomToast from "@/hooks/useCustomToast"
import useRadiusEnabled from "@/hooks/useRadiusEnabled"
import { handleError } from "@/utils"
import { Checkbox } from "../ui/checkbox"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog"
import { Field } from "../ui/field"
import { HostSelect } from "./HostSelect"
import { SAFE_KEY } from "./hostKeys"

const fieldGuideItems: FieldGuideItem[] = [
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
    icon: FiLayers,
    label: "Parent Host",
    description:
      "Optionally inherit from an existing host. The child is rendered with parent = <host> and inherits its key (and other settings) when it has none of its own.",
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

interface EditHostProps {
  host: HostPublic
}

interface HostUpdateForm {
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

const EditHost = ({ host }: EditHostProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    getValues,
    trigger,
    watch,
    control,
    formState: { errors, isSubmitting },
  } = useForm<HostUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...host,
      name: host.name ?? undefined,
      ipv4_address: host.ipv4_address ?? undefined,
      ipv6_address: host.ipv6_address ?? undefined,
      secret_key: host.secret_key ?? undefined,
      radius_secret_key: host.radius_secret_key ?? undefined,
      description: host.description ?? undefined,
      welcome_banner: host.welcome_banner ?? undefined,
      reject_banner: host.reject_banner ?? undefined,
      motd_banner: host.motd_banner ?? undefined,
      failed_authentication_banner:
        host.failed_authentication_banner ?? undefined,
      parent: host.parent ?? undefined,
      generate_config: host.generate_config ?? true,
    },
  })

  const parentValue = watch("parent")
  const radiusEnabled = useRadiusEnabled()
  // Shown while RADIUS is off only if the host already has one, so it can be
  // cleared; it is kept but not written to the config until RADIUS is on.
  const showRadiusSecret = radiusEnabled || !!host.radius_secret_key
  // RADIUS stays out of the guide while it is off. While it is on, a RADIUS
  // secret can stand in for the TACACS+ key, which is then not required.
  const guideItems = fieldGuideItems
    .filter((item) => showRadiusSecret || item.label !== "RADIUS Secret")
    .map((item) =>
      item.label === "Secret Key"
        ? { ...item, required: !showRadiusSecret }
        : item,
    )

  const mutation = useMutation({
    mutationFn: (data: HostUpdateForm) =>
      HostsService.updateHost({ id: host.id, hostUpdate: data }),
    onSuccess: () => {
      showSuccessToast("Host updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["hosts"] })
      queryClient.invalidateQueries({ queryKey: defaultCredentialsQueryKey })
    },
  })

  const onSubmit: SubmitHandler<HostUpdateForm> = async (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size="xl"
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost">
          <FaExchangeAlt fontSize="16px" />
          Edit Host
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit Host</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Grid templateColumns={{ base: "1fr", lg: "7fr 5fr" }} gap={6}>
              <GridItem>
                <Text mb={4} color="fg.muted" fontSize="sm">
                  Update the details for <strong>{host.name}</strong>.
                </Text>
                <VStack gap={4} as="section">
                  <Field
                    required
                    invalid={!!errors.name}
                    errorText={errors.name?.message}
                    label="Name"
                  >
                    <Input
                      {...register("name", {
                        required: "Name is required.",
                      })}
                      placeholder="core-switch-01"
                      type="text"
                    />
                  </Field>
                  <SimpleGrid columns={2} gap={4} w="full">
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
                      />
                    </Field>
                    <Field
                      invalid={!!errors.ipv6_address}
                      errorText={errors.ipv6_address?.message}
                      label="IPv6 Address"
                    >
                      <Input
                        {...register("ipv6_address")}
                        placeholder="2001:db8::1 (optional)"
                        type="text"
                      />
                    </Field>
                    <Field
                      required={!parentValue && !showRadiusSecret}
                      invalid={!!errors.secret_key}
                      errorText={errors.secret_key?.message}
                      label="Secret Key"
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
                            : "Shared secret key"
                        }
                        type="password"
                      />
                    </Field>
                    <Field
                      invalid={!!errors.parent}
                      errorText={errors.parent?.message}
                      label="Parent Host"
                    >
                      <HostSelect
                        value={parentValue}
                        onChange={(name) => {
                          setValue("parent", name, { shouldDirty: true })
                          if (errors.secret_key) trigger("secret_key")
                        }}
                        excludeId={host.id}
                      />
                    </Field>
                    {showRadiusSecret && (
                      <Field
                        invalid={!!errors.radius_secret_key}
                        errorText={errors.radius_secret_key?.message}
                        label="RADIUS Secret"
                        helperText={
                          radiusEnabled
                            ? "Optional. For devices that use RADIUS (e.g. MikroTik)."
                            : "RADIUS is disabled: this secret is kept but not used."
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
                          type="password"
                        />
                      </Field>
                    )}
                  </SimpleGrid>
                  <Field
                    invalid={!!errors.description}
                    errorText={errors.description?.message}
                    label="Description"
                  >
                    <Input
                      {...register("description")}
                      placeholder="Optional description"
                      type="text"
                    />
                  </Field>
                  <Controller
                    control={control}
                    name="generate_config"
                    render={({ field }) => (
                      <Field disabled={field.disabled} colorPalette="teal">
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={({ checked }) =>
                            field.onChange(checked)
                          }
                        >
                          Generate to TACACS+ Config
                        </Checkbox>
                      </Field>
                    )}
                  />
                  <Collapsible.Root style={{ width: "100%" }}>
                    <Collapsible.Trigger asChild>
                      <Button w="full" variant="outline" size="sm">
                        Configure Banner Messages
                      </Button>
                    </Collapsible.Trigger>
                    <Collapsible.Content>
                      <VStack gap={4} pt={4}>
                        <Field
                          invalid={!!errors.welcome_banner}
                          errorText={errors.welcome_banner?.message}
                          label="Welcome Banner"
                        >
                          <Textarea
                            {...register("welcome_banner")}
                            placeholder="Message shown on successful login"
                          />
                        </Field>
                        <Field
                          invalid={!!errors.reject_banner}
                          errorText={errors.reject_banner?.message}
                          label="Reject Banner"
                        >
                          <Textarea
                            {...register("reject_banner")}
                            placeholder="Message shown when access is denied"
                          />
                        </Field>
                        <Field
                          invalid={!!errors.motd_banner}
                          errorText={errors.motd_banner?.message}
                          label="MOTD Banner"
                        >
                          <Textarea
                            {...register("motd_banner")}
                            placeholder="Message of the day shown after login"
                          />
                        </Field>
                        <Field
                          invalid={!!errors.failed_authentication_banner}
                          errorText={
                            errors.failed_authentication_banner?.message
                          }
                          label="Failed Authentication Banner"
                        >
                          <Textarea
                            {...register("failed_authentication_banner")}
                            placeholder="Message shown on failed authentication"
                          />
                        </Field>
                      </VStack>
                    </Collapsible.Content>
                  </Collapsible.Root>
                </VStack>
              </GridItem>
              <GridItem>
                <FieldGuide
                  items={guideItems}
                  icon={FiServer}
                  subtitle="Learn what each field means and how it maps to the TACACS+ daemon configuration."
                  howItWorks="When you save a host block, it gets compiled into the server config definition for TACACS+ routing."
                />
              </GridItem>
            </Grid>
          </DialogBody>

          <DialogFooter gap={2}>
            <ButtonGroup>
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
                Update Host
              </Button>
            </ButtonGroup>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default EditHost
