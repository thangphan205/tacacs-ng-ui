import {
  Button,
  ButtonGroup,
  DialogActionTrigger,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"

import { type ApiError, type TacacsNgSettingPublic, TacacsNgSettingsService } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
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

interface EditTacacsNgSettingProps {
  tacacs_ng_setting: TacacsNgSettingPublic
}

interface TacacsNgSettingUpdateForm {
  ipv4_address: string
  ipv4_port?: number
  instances_min: number
  instances_max: number
  background: string
  access_logfile_destination: string
  accounting_logfile_destination: string
  authentication_logfile_destination: string
  login_backend: string
  user_backend: string
  pap_backend: string
}

const EditTacacsNgSetting = ({ tacacs_ng_setting }: EditTacacsNgSettingProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TacacsNgSettingUpdateForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...tacacs_ng_setting,
      ipv4_address: tacacs_ng_setting.ipv4_address ?? undefined,
      ipv4_port: tacacs_ng_setting.ipv4_port ?? undefined,
      instances_min: tacacs_ng_setting.instances_min ?? undefined,
      instances_max: tacacs_ng_setting.instances_max ?? undefined,
      background: tacacs_ng_setting.background ?? undefined,
      access_logfile_destination: tacacs_ng_setting.access_logfile_destination ?? undefined,
      accounting_logfile_destination: tacacs_ng_setting.accounting_logfile_destination ?? undefined,
      authentication_logfile_destination: tacacs_ng_setting.authentication_logfile_destination ?? undefined,
      login_backend: tacacs_ng_setting.login_backend ?? undefined,
      user_backend: tacacs_ng_setting.user_backend ?? undefined,
      pap_backend: tacacs_ng_setting.pap_backend ?? undefined,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: TacacsNgSettingUpdateForm) =>
      TacacsNgSettingsService.updateTacacsNgSettings({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("TacacsNgSetting updated successfully.")
      reset()
      setIsOpen(false)
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tacacs_ng_settings"] })
    },
  })

  const onSubmit: SubmitHandler<TacacsNgSettingUpdateForm> = async (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost">
          <FaExchangeAlt fontSize="16px" />
          Edit TacacsNgSetting
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>Edit TacacsNgSetting</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Text mb={4}>Update the item details below.</Text>
            <VStack gap={4}>
              <Field
                required
                invalid={!!errors.ipv4_address}
                errorText={errors.ipv4_address?.message}
                label="ipv4_address"
              >
                <Input
                  {...register("ipv4_address", {
                    required: "ipv4_address is required",
                  })}
                  placeholder="ipv4_address"
                  type="text"
                />
              </Field>
              <Field
                required
                invalid={!!errors.ipv4_port}
                errorText={errors.ipv4_port?.message}
                label="ipv4_port"
              >
                <Input
                  {...register("ipv4_port", {
                    required: "action is required",
                  })}
                  placeholder="ipv4_port"
                  type="number"
                />
              </Field>
              <Field
                invalid={!!errors.instances_min}
                errorText={errors.instances_min?.message}
                label="instances_min"
              >
                <Input
                  {...register("instances_min")}
                  placeholder="1"
                  type="number"
                />
              </Field>
              <Field
                invalid={!!errors.instances_max}
                errorText={errors.instances_max?.message}
                label="instances_max"
              >
                <Input
                  {...register("instances_max")}
                  placeholder="10"
                  type="number"
                />
              </Field>
              <Field
                required
                invalid={!!errors.access_logfile_destination}
                errorText={errors.access_logfile_destination?.message}
                label="access_logfile_destination"
              >
                <Input
                  {...register("access_logfile_destination", {
                    required: "access_logfile_destination is required",
                  })}
                  placeholder="access_logfile_destination"
                  type="text"
                />
              </Field>

              <Field
                required
                invalid={!!errors.accounting_logfile_destination}
                errorText={errors.accounting_logfile_destination?.message}
                label="accounting_logfile_destination"
              >
                <Input
                  {...register("accounting_logfile_destination", {
                    required: "accounting_logfile_destination is required",
                  })}
                  placeholder="accounting_logfile_destination"
                  type="text"
                />
              </Field>
              <Field
                required
                invalid={!!errors.authentication_logfile_destination}
                errorText={errors.authentication_logfile_destination?.message}
                label="authentication_logfile_destination"
              >
                <Input
                  {...register("authentication_logfile_destination", {
                    required: "authentication_logfile_destination is required",
                  })}
                  placeholder="authentication_logfile_destination"
                  type="text"
                />
              </Field>
              <Field
                required
                invalid={!!errors.login_backend}
                errorText={errors.login_backend?.message}
                label="login_backend"
              >
                <Input
                  {...register("login_backend", {
                    required: "login_backend is required",
                  })}
                  placeholder="login_backend"
                  type="text"
                />
              </Field>
              <Field
                required
                invalid={!!errors.user_backend}
                errorText={errors.user_backend?.message}
                label="user_backend"
              >
                <Input
                  {...register("user_backend", {
                    required: "user_backend is required",
                  })}
                  placeholder="user_backend"
                  type="text"
                />
              </Field>
              <Field
                required
                invalid={!!errors.pap_backend}
                errorText={errors.pap_backend?.message}
                label="pap_backend"
              >
                <Input
                  {...register("pap_backend", {
                    required: "pap_backend is required",
                  })}
                  placeholder="pap_backend"
                  type="text"
                />
              </Field>
            </VStack>
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
                Save
              </Button>
            </ButtonGroup>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default EditTacacsNgSetting
