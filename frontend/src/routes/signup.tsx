import {
  Container,
  Flex,
  HStack,
  Icon,
  Image,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FiCheck, FiLock, FiUser } from "react-icons/fi"

import type { UserRegister } from "@/client"
import { Button } from "@/components/ui/button"
import { Field } from "@/components/ui/field"
import { InputGroup } from "@/components/ui/input-group"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { confirmPasswordRules, emailPattern } from "@/utils"
import Logo from "/assets/images/tacacs-ng-ui.svg"

export const Route = createFileRoute("/signup")({
  component: SignUp,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
})

interface UserRegisterForm extends UserRegister {
  confirm_password: string
}

function SignUp() {
  const { signUpMutation } = useAuth()
  const {
    register,
    handleSubmit,
    getValues,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<UserRegisterForm>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      full_name: "",
      password: "",
      confirm_password: "",
    },
  })

  const password = watch("password", "")
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

  const onSubmit: SubmitHandler<UserRegisterForm> = (data) => {
    signUpMutation.mutate(data)
  }

  return (
    <Flex flexDir={{ base: "column", md: "row" }} justify="center" h="100vh">
      <Container
        as="form"
        onSubmit={handleSubmit(onSubmit)}
        h="100vh"
        maxW="sm"
        alignItems="stretch"
        justifyContent="center"
        gap={4}
        centerContent
      >
        <Image
          src={Logo}
          alt="FastAPI logo"
          height="auto"
          maxW="2xs"
          alignSelf="center"
          mb={4}
        />
        <Field
          invalid={!!errors.full_name}
          errorText={errors.full_name?.message}
        >
          <InputGroup w="100%" startElement={<FiUser />}>
            <Input
              minLength={3}
              {...register("full_name", {
                required: "Full Name is required",
              })}
              placeholder="Full Name"
              type="text"
            />
          </InputGroup>
        </Field>

        <Field invalid={!!errors.email} errorText={errors.email?.message}>
          <InputGroup w="100%" startElement={<FiUser />}>
            <Input
              {...register("email", {
                required: "Email is required",
                pattern: emailPattern,
              })}
              placeholder="Email"
              type="email"
            />
          </InputGroup>
        </Field>
        <PasswordInput
          type="password"
          startElement={<FiLock />}
          {...register("password", {
            required: "Password is required.",
            minLength: {
              value: 12,
              message: "Password must be at least 12 characters long.",
            },
            validate: {
              hasLower: (value) =>
                /[a-z]/.test(value) || "Must contain one lowercase letter.",
              hasUpper: (value) =>
                /[A-Z]/.test(value) || "Must contain one uppercase letter.",
              hasNumber: (value) => /[0-9]/.test(value) || "Must contain one number.",
              hasSpecial: (value) =>
                /[!\"#$%&'()*+,-./:;<=>?@\[\\\]^_`{|}~]/.test(value) || "Must contain one special character.",
            },
          })}
          placeholder="Password"
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
            const isMet = policy.regex.test(password)
            return (
              <HStack key={index} color={isMet ? "green" : "gray.500"}>
                < Icon as={FiCheck} />
                <Text as="span" fontSize="md">
                  {policy.text}
                </Text>
              </HStack>
            )
          })}
        </VStack>

        <Button variant="solid" type="submit" loading={isSubmitting}>
          Sign Up
        </Button>
        <Text>
          Already have an account?{" "}
          <RouterLink to="/login" className="main-link">
            Log In
          </RouterLink>
        </Text>
      </Container>
    </Flex >
  )
}

export default SignUp
