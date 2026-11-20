import {
  Button,
  createListCollection,
  DialogTitle,
  Input,
  Select,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { Controller, type SubmitHandler, useForm } from "react-hook-form"
import { FiRadio } from "react-icons/fi"

import type { ApiError } from "@/api"
import {
  type ProfilePublic,
  type ProfileScriptPublic,
  ProfilescriptsetsService,
  ProfilescriptsService,
} from "@/client"
import {
  DialogActionTrigger,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Field } from "@/components/ui/field"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface Preset {
  attribute: string
  label: string
  hint: string
  example: string
}

// Attributes from the built-in dictionary (backend/app/core/radius_dictionary.cfg).
const PRESETS: Preset[] = [
  {
    attribute: "radius[MikroTik:MikroTik-Group]",
    label: "MikroTik — user group",
    hint: "Name of a RouterOS user group: full, write, read or your own.",
    example: "full",
  },
  {
    attribute: "radius[Cisco:Cisco-AVPair]",
    label: "Cisco — AV pair",
    hint: "For example shell:priv-lvl=15.",
    example: "shell:priv-lvl=15",
  },
  {
    attribute: "radius[Fortinet:Fortinet-Access-Profile]",
    label: "Fortinet — admin profile",
    hint: "Name of a FortiGate admin profile.",
    example: "super_admin",
  },
  {
    attribute: "radius[PaloAlto:PaloAlto-Admin-Role]",
    label: "Palo Alto — admin role",
    hint: "Name of an admin role profile.",
    example: "superuser",
  },
  {
    attribute: "radius[Juniper:Juniper-Local-User-Name]",
    label: "Juniper — local user template",
    hint: "Name of a local user template on the device.",
    example: "super-user-template",
  },
  {
    attribute: "radius[Aruba:Aruba-Admin-Role]",
    label: "Aruba — admin role",
    hint: "Name of a management role.",
    example: "root",
  },
  {
    attribute: "radius[Huawei:Huawei-Exec-Privilege]",
    label: "Huawei — exec privilege",
    hint: "Privilege level, 0-15.",
    example: "15",
  },
  {
    attribute: "radius[Reply-Message]",
    label: "Reply-Message",
    hint: "Text the device may show the user.",
    example: "Welcome",
  },
]

const presetCollection = createListCollection({
  items: PRESETS.map((p) => ({ label: p.label, value: p.attribute })),
})

/** A value tac_plus-ng reads as one token stays bare; anything else is quoted. */
function configValue(value: string): string {
  return /^[A-Za-z0-9_.-]+$/.test(value) ? value : `"${value}"`
}

/** The script a RADIUS reply attribute belongs on: `if (aaa.protocol == radius)`. */
function findRadiusScript(
  scripts: ProfileScriptPublic[],
): ProfileScriptPublic | undefined {
  return scripts.find(
    (s) =>
      s.condition === "if" &&
      s.key.trim() === "aaa.protocol" &&
      s.value.trim() === "radius",
  )
}

interface FormValues {
  attribute: string
  value: string
}

const AddRadiusAttribute = ({
  profile,
  scripts,
}: {
  profile: ProfilePublic
  scripts: ProfileScriptPublic[]
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const existing = findRadiusScript(scripts)
  const {
    control,
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    mode: "onBlur",
    defaultValues: { attribute: PRESETS[0].attribute, value: "" },
  })
  const preset = PRESETS.find((p) => p.attribute === watch("attribute"))

  const mutation = useMutation({
    mutationFn: async (data: FormValues) => {
      // One RADIUS branch per profile: tac_plus-ng stops at its permit, so a
      // second `if (aaa.protocol == radius)` below it would never be reached.
      const script =
        existing ??
        (await ProfilescriptsService.createProfilescript({
          profileScriptCreate: {
            condition: "if",
            key: "aaa.protocol",
            value: "radius",
            action: "permit",
            description: "RADIUS reply attributes",
            profile_id: profile.id,
          },
        }))
      await ProfilescriptsetsService.createProfilescriptset({
        profileScriptSetCreate: {
          key: data.attribute,
          value: configValue(data.value.trim()),
          profilescript_id: script.id,
        },
      })
    },
    onSuccess: () => {
      showSuccessToast("RADIUS attribute added.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["profilescripts"] })
      queryClient.invalidateQueries({ queryKey: ["profilescriptsets"] })
    },
  })

  const onSubmit: SubmitHandler<FormValues> = (data) => mutation.mutate(data)

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">
          <FiRadio fontSize="16px" />
          Add RADIUS Attribute
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Add RADIUS Attribute</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4} fontSize="sm" color="fg.muted">
              Returned to RADIUS devices that sign users in with the{" "}
              <strong>{profile.name}</strong> profile.{" "}
              {existing
                ? "It is added to the profile's existing RADIUS script."
                : "This adds a script: if aaa.protocol == radius, set the attribute and permit."}
            </Text>
            <VStack gap={4}>
              <Controller
                control={control}
                name="attribute"
                render={({ field }) => (
                  <Field label="Attribute" helperText={preset?.hint}>
                    <Select.Root
                      collection={presetCollection}
                      size="sm"
                      value={[field.value]}
                      onValueChange={({ value }) => field.onChange(value[0])}
                    >
                      <Select.Trigger>
                        <Select.ValueText />
                      </Select.Trigger>
                      <Select.Positioner>
                        <Select.Content>
                          {presetCollection.items.map((item) => (
                            <Select.Item key={item.value} item={item}>
                              {item.label}
                              <Select.ItemIndicator />
                            </Select.Item>
                          ))}
                        </Select.Content>
                      </Select.Positioner>
                    </Select.Root>
                  </Field>
                )}
              />
              <Field
                label="Value"
                required
                invalid={!!errors.value}
                errorText={errors.value?.message}
              >
                <Input
                  {...register("value", {
                    required: "Value is required.",
                    validate: (v) =>
                      !/["\\\r\n]/.test(v) ||
                      "Value can't contain quotes, backslashes or line breaks.",
                  })}
                  placeholder={preset?.example}
                />
              </Field>
            </VStack>
          </DialogBody>
          <DialogFooter gap={2}>
            <DialogActionTrigger asChild>
              <Button
                variant="subtle"
                colorPalette="gray"
                disabled={isSubmitting}
              >
                Cancel
              </Button>
            </DialogActionTrigger>
            <Button type="submit" loading={isSubmitting}>
              Add
            </Button>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default AddRadiusAttribute
