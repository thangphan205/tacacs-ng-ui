import {
  Box,
  Button,
  Container,
  Heading,
  HStack,
  Icon,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation } from "@tanstack/react-query"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FiCheck, FiLock } from "react-icons/fi"

import { type ApiError, type UpdatePassword, UsersService } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { confirmPasswordRules, handleError } from "@/utils"
import { PasswordInput } from "../ui/password-input"

interface UpdatePasswordForm extends UpdatePassword {
  confirm_password: string
}

const ChangePassword = () => {
  const { showSuccessToast } = useCustomToast()
  const {
    register,
    handleSubmit,
    reset,
    getValues,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<UpdatePasswordForm>({
    mode: "onBlur",
    criteriaMode: "all",
  })

  const newPassword = watch("new_password", "")
  const passwordPolicies = [
    {
      text: "At least 12 characters",
      regex: /^.{12,}$/,
    },
    {
      text: "One lowercase letter (a-z)",
      regex: /[a-z]/,
    },
    {
      text: "One uppercase letter (A-Z)",
      regex: /[A-Z]/,
    },
    {
      text: "One number (0-9)",
      regex: /[0-9]/,
    },
    {
      text: "One special character (e.g. !@#$%)",
      regex: /[!\"#$%&'()*+,-./:;<=>?@\[\\\]^_`{|}~]/,
    },
  ]

  const mutation = useMutation({
    mutationFn: (data: UpdatePassword) =>
      UsersService.updatePasswordMe({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("Password updated successfully.")
      reset()
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
  })

  const onSubmit: SubmitHandler<UpdatePasswordForm> = async (data) => {
    mutation.mutate(data)
  }

  return (
    <Container maxW="full">
      <Heading size="sm" py={4}>
        Change Password
      </Heading>
      <Box as="form" onSubmit={handleSubmit(onSubmit)}>
        <VStack gap={4} w={{ base: "100%", md: "sm" }}>
          <PasswordInput
            type="current_password"
            startElement={<FiLock />}
            {...register("current_password", {
              required: "Current password is required.",
            })}
            placeholder="Current Password"
            errors={errors}
          />
          <PasswordInput
            type="new_password"
            startElement={<FiLock />}
            {...register("new_password", {
              required: "New password is required.",
              minLength: {
                value: 12,
                message: "Password must be at least 12 characters long.",
              },
              validate: {
                hasLower: (value) =>
                  /[a-z]/.test(value) || "Must contain one lowercase letter.",
                hasUpper: (value) =>
                  /[A-Z]/.test(value) || "Must contain one uppercase letter.",
                hasNumber: (value) =>
                  /[0-9]/.test(value) || "Must contain one number.",
                hasSpecial: (value) =>
                  /[!\"#$%&'()*+,-./:;<=>?@\[\\\]^_`{|}~]/.test(value) || "Must contain one special character.",
              },
            })}
            placeholder="New Password"
            errors={errors}
          />
          <PasswordInput
            type="confirm_password"
            startElement={<FiLock />}
            {...register("confirm_password", confirmPasswordRules(getValues))}
            placeholder="Confirm Password"
            errors={errors}
          />
          <VStack align="start" w="full" color="gray.500" fontSize="sm">
            <Text>Password must contain at least:</Text>
            {passwordPolicies.map((policy, index) => {
              const isMet = policy.regex.test(newPassword)
              return (
                <HStack key={index} color={isMet ? "green.500" : "gray.500"}>
                  <Icon as={FiCheck} />
                  <Text as="span" fontSize="sm">
                    {policy.text}
                  </Text>
                </HStack>
              )
            })}
          </VStack>
        </VStack>
        <Button variant="solid" mt={4} type="submit" loading={isSubmitting}>
          Save
        </Button>
      </Box>
    </Container>
  )
}
export default ChangePassword
