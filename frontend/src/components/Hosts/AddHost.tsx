import {
  Box,
  Button,
  DialogActionTrigger,
  DialogTitle,
  Flex,
  HStack,
  Text,
} from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FiPlus, FiServer } from "react-icons/fi"
import type { ApiError } from "@/api"
import { type HostCreate, HostsService } from "@/client"
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
  DialogTrigger,
} from "../ui/dialog"
import { HostForm, type HostFormValues } from "./HostForm"

const AddHost = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const form = useForm<HostFormValues>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "",
      ipv4_address: "",
      ipv6_address: "",
      secret_key: "",
      radius_secret_key: "",
      description: "",
      welcome_banner: "",
      reject_banner: "",
      motd_banner: "",
      failed_authentication_banner: "",
      parent: "",
      generate_config: true,
    },
  })

  const {
    handleSubmit,
    reset,
    formState: { isValid, isSubmitting },
  } = form

  const radiusEnabled = useRadiusEnabled()

  const mutation = useMutation({
    mutationFn: (data: HostCreate) =>
      HostsService.createHost({ hostCreate: data }),
    onSuccess: () => {
      showSuccessToast("Host created successfully.")
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

  const onSubmit: SubmitHandler<HostFormValues> = (data) => {
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
        <Button value="add-item" my={4}>
          <FiPlus fontSize="16px" />
          Add Host
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
                  Add Host
                </DialogTitle>
                <Text color="fg.muted" fontSize="xs" mt={0.5}>
                  Add a network device that will authenticate against the
                  TACACS+ server.
                </Text>
              </Box>
            </HStack>
          </DialogHeader>

          <DialogBody py={5}>
            <HostForm
              form={form}
              radiusEnabled={Boolean(radiusEnabled)}
              showRadiusSecret={Boolean(radiusEnabled)}
              howItWorks='When you save a host with "Generate to Config" enabled, the system creates a host block in the TACACS+ daemon config using the Name, IPv4 Address, and Secret Key you provide.'
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
            <Flex gap={2} ml="auto">
              <DialogActionTrigger asChild>
                <Button
                  variant="subtle"
                  colorPalette="gray"
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
              </DialogActionTrigger>
              <Button
                variant="solid"
                type="submit"
                disabled={!isValid}
                loading={isSubmitting}
              >
                Add Host
              </Button>
            </Flex>
          </DialogFooter>
        </form>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default AddHost
