import {
  Box,
  Button,
  Container,
  EmptyState,
  Flex,
  Heading,
  Input,
  SimpleGrid,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect } from "react"
import { useForm, type SubmitHandler } from "react-hook-form"
import { FiSettings } from "react-icons/fi"

import {
  type ApiError,
  type TacacsNgSettingUpdate,
  TacacsNgSettingsService,
} from "@/client"
import PendingTacacsNgSettings from "@/components/Pending/PendingTacacsNgSettings"
import { Field } from "@/components/ui/field"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

function getTacacsNgSettingsQueryOptions() {
  return {
    queryFn: () => TacacsNgSettingsService.readTacacsNgSettings(),
    queryKey: ["tacacs_ng_settings"],
  }
}

export const Route = createFileRoute("/_layout/tacacs_ng_settings")({
  component: TacacsNgSettings,
})

function TacacsNgSettingsForm() {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const { data: settings, isLoading } = useQuery({
    ...getTacacsNgSettingsQueryOptions(),
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<TacacsNgSettingUpdate>({
    mode: "onBlur",
    criteriaMode: "all",
  })

  useEffect(() => {
    if (settings) {
      reset(settings)
    }
  }, [settings, reset])

  const mutation = useMutation({
    mutationFn: (data: TacacsNgSettingUpdate) =>
      TacacsNgSettingsService.updateTacacsNgSettings({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("TACACS+ NG Settings updated successfully.")
      queryClient.invalidateQueries({ queryKey: ["tacacs_ng_settings"] })
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
  })

  const onSubmit: SubmitHandler<TacacsNgSettingUpdate> = async (data) => {
    mutation.mutate(data)
  }

  if (isLoading) {
    return <PendingTacacsNgSettings />
  }

  if (!settings) {
    return (
      <EmptyState.Root>
        <EmptyState.Content>
          <EmptyState.Indicator>
            <FiSettings />
          </EmptyState.Indicator>
          <VStack textAlign="center">
            <EmptyState.Title>
              TACACS+ NG Settings not found
            </EmptyState.Title>
            <EmptyState.Description>
              Settings have not been configured yet.
            </EmptyState.Description>
          </VStack>
        </EmptyState.Content>
      </EmptyState.Root>
    )
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <Box mt={4} p={4} borderWidth="1px" borderRadius="lg">
        <VStack align="stretch" >
          <SimpleGrid columns={{ base: 1, md: 2 }} >
            <Field
              label="IPv4 Address"
              required
              errorText={errors.ipv4_address?.message}
            >
              <Input
                {...register("ipv4_address", {
                  required: "IPv4 Address is required.",
                })}
                type="text"
              />
            </Field>
            <Field
              label="IPv4 Port"
              required
              errorText={errors.ipv4_port?.message}
            >
              <Input
                {...register("ipv4_port", {
                  required: "IPv4 Port is required.",
                  valueAsNumber: true,
                })}
                type="number"
              />
            </Field>
            <Field
              label="Min Instances"
              required
              errorText={errors.instances_min?.message}
            >
              <Input
                {...register("instances_min", {
                  required: "Min instances is required.",
                  valueAsNumber: true,
                })}
                type="number"
              />
            </Field>
            <Field
              label="Max Instances"
              required
              errorText={errors.instances_max?.message}
            >
              <Input
                {...register("instances_max", {
                  required: "Max instances is required.",
                  valueAsNumber: true,
                })}
                type="number"
              />
            </Field>
            <Field
              label="Login Backend"
              errorText={errors.login_backend?.message}
            >
              <Input
                {...register("login_backend")}
                type="text"
              />
            </Field>
          </SimpleGrid>
          <Flex justifyContent="flex-end">
            <Button
              type="submit"
              colorScheme="blue"
              loading={isSubmitting}
              disabled={!isDirty}
            >
              Save
            </Button>
          </Flex>
        </VStack>
      </Box>
    </form >
  )
}

function TacacsNgSettings() {
  return (
    <Container maxW="full">
      <Heading size="lg" pt={12} mb={4}>
        TACACS+ NG Settings
      </Heading>
      <TacacsNgSettingsForm />
    </Container>
  )
}
