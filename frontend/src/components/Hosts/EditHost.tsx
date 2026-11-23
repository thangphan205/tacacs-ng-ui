import {
  Box,
  Button,
  ButtonGroup,
  DialogActionTrigger,
  HStack,
  Text,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FaExchangeAlt } from "react-icons/fa"
import { FiServer } from "react-icons/fi"
import type { ApiError } from "@/api"
import { type HostPublic, HostsService } from "@/client"
import { defaultCredentialsQueryKey } from "@/components/Common/DefaultCredentialsAlert"
import useCustomToast from "@/hooks/useCustomToast"
import useRadiusEnabled from "@/hooks/useRadiusEnabled"
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
import { HostForm, type HostFormValues } from "./HostForm"

interface EditHostProps {
  host: HostPublic
}

const EditHost = ({ host }: EditHostProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const form = useForm<HostFormValues>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: host.name ?? "",
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

  const {
    handleSubmit,
    reset,
    formState: { isSubmitting },
  } = form

  const radiusEnabled = useRadiusEnabled()
  // Shown while RADIUS is off only if the host already has one, so it can be
  // cleared; it is kept but not written to the config until RADIUS is on.
  const showRadiusSecret = radiusEnabled || !!host.radius_secret_key

  const mutation = useMutation({
    mutationFn: (data: HostFormValues) =>
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

  const onSubmit: SubmitHandler<HostFormValues> = async (data) => {
    mutation.mutate(data)
  }

  return (
    <DialogRoot
      size="xl"
      placement="center"
      scrollBehavior="inside"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost">
          <FaExchangeAlt fontSize="16px" />
          Edit Host
        </Button>
      </DialogTrigger>
      <DialogContent overflow="hidden">
        <form
          onSubmit={handleSubmit(onSubmit)}
          style={{
            display: "flex",
            flexDirection: "column",
            maxHeight: "inherit",
            minHeight: 0,
            flex: 1,
          }}
        >
          <DialogHeader
            pb={4}
            borderBottomWidth="1px"
            borderColor="border.subtle"
          >
            <HStack gap={3} align="center">
              <Box
                p={2.5}
                borderRadius="xl"
                bg="teal.muted"
                color="teal.fg"
                flexShrink={0}
              >
                <FiServer size={18} />
              </Box>
              <Box>
                <DialogTitle fontSize="lg" fontWeight="bold" lineHeight="1.2">
                  Edit Host
                </DialogTitle>
                <Text color="fg.muted" fontSize="xs" mt={0.5}>
                  Update the details for <strong>{host.name}</strong>.
                </Text>
              </Box>
            </HStack>
          </DialogHeader>

          <DialogBody py={5}>
            <HostForm
              form={form}
              radiusEnabled={Boolean(radiusEnabled)}
              showRadiusSecret={showRadiusSecret}
              existingName={host.name}
              excludeHostId={host.id}
              howItWorks="When you save a host block, it gets compiled into the server config definition for TACACS+ routing."
            />
          </DialogBody>

          <DialogFooter
            pt={4}
            borderTopWidth="1px"
            borderColor="border.subtle"
            justifyContent="space-between"
          >
            <Text
              fontSize="xs"
              color="fg.muted"
              display={{ base: "none", sm: "block" }}
            >
              Fields marked with{" "}
              <Text as="span" color="red.500">
                *
              </Text>{" "}
              are required.
            </Text>
            <ButtonGroup ml="auto">
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
