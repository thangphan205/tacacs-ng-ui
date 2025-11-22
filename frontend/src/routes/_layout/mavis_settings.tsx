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
    type MavisUpdate,
    MavisService,
} from "@/client"
import PendingMavisSettings from "@/components/Pending/PendingMavisSettings"
import { Field } from "@/components/ui/field"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

function getMavisSettingsQueryOptions() {
    return {
        queryFn: () => MavisService.readMavisSettings(),
        queryKey: ["mavis_settings"],
    }
}

export const Route = createFileRoute("/_layout/mavis_settings")({
    component: MavisSettings,
})

function MavisSettingsForm() {
    const queryClient = useQueryClient()
    const { showSuccessToast } = useCustomToast()
    const { data: settings, isLoading } = useQuery({
        ...getMavisSettingsQueryOptions(),
    })

    const {
        register,
        handleSubmit,
        reset,
        formState: { errors, isSubmitting, isDirty },
    } = useForm<MavisUpdate>({
        mode: "onBlur",
        criteriaMode: "all",
    })

    useEffect(() => {
        if (settings) {
            reset(settings)
        }
    }, [settings, reset])

    const mutation = useMutation({
        mutationFn: (data: MavisUpdate) =>
            MavisService.updateMavisSettings({ requestBody: data }),
        onSuccess: () => {
            showSuccessToast("Mavis Settings updated successfully.")
            queryClient.invalidateQueries({ queryKey: ["mavis_settings"] })
        },
        onError: (err: ApiError) => {
            handleError(err)
        },
    })

    const onSubmit: SubmitHandler<MavisUpdate> = async (data) => {
        mutation.mutate(data)
    }

    if (isLoading) {
        return <PendingMavisSettings />
    }

    if (!settings) {
        return (
            <EmptyState.Root>
                <EmptyState.Content>
                    <EmptyState.Indicator>
                        <FiSettings />
                    </EmptyState.Indicator>
                    <VStack textAlign="center">
                        <EmptyState.Title>Mavis Settings not found</EmptyState.Title>
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
            <Box mt={4} p={4} borderWidth="1px" borderRadius="lg" boxShadow="sm">
                <VStack align="stretch" >
                    <SimpleGrid columns={{ base: 1, md: 2 }} >
                        <Field label="LDAP Server Type" required errorText={errors.ldap_server_type?.message}>
                            <Input {...register("ldap_server_type", { required: "LDAP Server Type is required." })} type="text" />
                        </Field>
                        <Field label="LDAP Hosts" required errorText={errors.ldap_hosts?.message}>
                            <Input {...register("ldap_hosts", { required: "LDAP Hosts is required." })} type="text" />
                        </Field>
                        <Field label="LDAP Base" required errorText={errors.ldap_base?.message}>
                            <Input {...register("ldap_base", { required: "LDAP Base is required." })} type="text" />
                        </Field>
                        <Field label="LDAP User" required errorText={errors.ldap_user?.message}>
                            <Input {...register("ldap_user", { required: "LDAP User is required." })} type="text" />
                        </Field>
                        <Field label="LDAP Password" required errorText={errors.ldap_passwd?.message}>
                            <Input {...register("ldap_passwd", { required: "LDAP Password is required." })} type="password" />
                        </Field>
                        <Field label="LDAP Filter" required errorText={errors.ldap_filter?.message}>
                            <Input {...register("ldap_filter", { required: "LDAP Filter is required." })} type="text" />
                        </Field>
                        <Field label="LDAP Timeout" required errorText={errors.ldap_timeout?.message}>
                            <Input
                                {...register("ldap_timeout", {
                                    required: "LDAP Timeout is required.",
                                    valueAsNumber: true,
                                })}
                                type="number"
                            />
                        </Field>
                        <Field
                            label="Require TACACS Group Prefix"
                            required
                            errorText={errors.require_tacacs_group_prefix?.message}
                        >
                            <Input
                                {...register("require_tacacs_group_prefix", {
                                    required: "This field is required.",
                                    valueAsNumber: true,
                                })}
                                type="number"
                            />
                        </Field>
                        <Field
                            label="TACACS Group Prefix"
                            required
                            errorText={errors.tacacs_group_prefix?.message}
                        >
                            <Input
                                {...register("tacacs_group_prefix", {
                                    required: "TACACS Group Prefix is required.",
                                })}
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
        </form>
    )
}

function MavisSettings() {
    return (
        <Container maxW="full">
            <Heading size="lg" pt={12} mb={4}>
                Mavis Settings
            </Heading>
            <MavisSettingsForm />
        </Container>
    )
}