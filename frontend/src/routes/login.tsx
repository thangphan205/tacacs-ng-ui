import {
  Box,
  Flex,
  Icon,
  Image,
  Input,
  Link,
  Separator,
  Text,
} from "@chakra-ui/react"
import { startAuthentication } from "@simplewebauthn/browser"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
  useNavigate,
} from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FcGoogle } from "react-icons/fc"
import { FiGithub } from "react-icons/fi"

import type { Body_login_login_access_token as AccessToken } from "@/client"
import { OpenAPI } from "@/client"
import { Button } from "@/components/ui/button"
import { Field } from "@/components/ui/field"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { handleError } from "@/utils"
import Logo from "/assets/images/tacacs-ng-ui-logo.svg"
import { version } from "../../package.json"
import { emailPattern, passwordRules } from "../utils"

interface ProvidersStatus {
  google: boolean
  keycloak: boolean
  passkey: boolean
}

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({ to: "/" })
    }
  },
})

function Login() {
  const { loginMutation, error, resetError } = useAuth()
  const navigate = useNavigate()
  const [providers, setProviders] = useState<ProvidersStatus>({
    google: false,
    keycloak: false,
    passkey: false,
  })

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AccessToken>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { username: "", password: "" },
  })

  useEffect(() => {
    fetch(`${OpenAPI.BASE}/api/v1/auth-providers/status`)
      .then((r) => r.json())
      .then((data: ProvidersStatus) => setProviders(data))
      .catch(() => {})
  }, [])

  const handleGoogleLogin = async () => {
    try {
      const res = await fetch(`${OpenAPI.BASE}/api/v1/oauth/google/authorize`)
      const data = await res.json()
      if (!res.ok || !data.url) {
        handleError({ status: res.status, body: data } as never)
        return
      }
      window.location.href = data.url
    } catch {
      handleError({
        status: 0,
        body: { detail: "Could not reach the server." },
      } as never)
    }
  }

  const handleKeycloakLogin = async () => {
    try {
      const res = await fetch(`${OpenAPI.BASE}/api/v1/oauth/keycloak/authorize`)
      const data = await res.json()
      if (!res.ok || !data.url) {
        handleError({ status: res.status, body: data } as never)
        return
      }
      window.location.href = data.url
    } catch {
      handleError({
        status: 0,
        body: { detail: "Could not reach the server." },
      } as never)
    }
  }

  const handlePasskeyLogin = async () => {
    try {
      const beginRes = await fetch(
        `${OpenAPI.BASE}/api/v1/passkeys/authenticate/begin`,
        {
          method: "POST",
        },
      )
      if (!beginRes.ok)
        throw new Error("Failed to begin passkey authentication")
      const options = await beginRes.json()

      const credential = await startAuthentication({ optionsJSON: options })

      const completeRes = await fetch(
        `${OpenAPI.BASE}/api/v1/passkeys/authenticate/complete`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ credential }),
        },
      )
      if (!completeRes.ok) {
        const err = await completeRes.json()
        throw new Error(err.detail ?? "Passkey authentication failed")
      }
      const tokenData = await completeRes.json()
      localStorage.setItem("access_token", tokenData.access_token)
      navigate({ to: "/" })
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "NotAllowedError") return
      handleError({
        status: 0,
        body: { detail: (err as Error).message },
      } as never)
    }
  }

  const onSubmit: SubmitHandler<AccessToken> = async (data) => {
    if (isSubmitting) return
    resetError()
    try {
      await loginMutation.mutateAsync(data)
    } catch {
      // error is handled by useAuth hook
    }
  }

  const hasOAuthProviders =
    providers.google || providers.keycloak || providers.passkey

  return (
    <Flex h="100vh" w="100vw" overflow="hidden" direction="row">
      {/* Left Pane - Brand/Logo (hidden on mobile, centered on desktop) */}
      <Flex
        flex="1"
        bg="gray.50"
        align="center"
        justify="center"
        display={{ base: "none", md: "flex" }}
        h="full"
        p={8}
      >
        <Image
          src={Logo}
          alt="FastAPI logo"
          height="auto"
          maxW="xs"
          alignSelf="center"
        />
      </Flex>

      {/* Right Pane - Login Form */}
      <Flex
        flex="1"
        bg="bg"
        align="center"
        justify="center"
        h="full"
        p={{ base: 6, md: 12 }}
      >
        <Box
          as="form"
          onSubmit={handleSubmit(onSubmit)}
          w="full"
          maxW="sm"
          display="flex"
          flexDirection="column"
          gap={5}
        >
          <Text
            as="h1"
            fontSize="2xl"
            fontWeight="bold"
            textAlign="center"
            color="teal.600"
            mb={2}
          >
            Login to your account
          </Text>

          <Field
            label="Email"
            invalid={!!errors.username}
            errorText={errors.username?.message || !!error}
          >
            <Input
              {...register("username", {
                required: "Username is required",
                pattern: emailPattern,
              })}
              placeholder="user@example.com"
              type="email"
              size="md"
            />
          </Field>

          <PasswordInput
            type="password"
            label={
              <Flex justify="space-between" align="center" w="full">
                <Text as="span">Password</Text>
                <Link
                  asChild
                  fontSize="xs"
                  fontWeight="medium"
                  color="gray.600"
                  _hover={{ textDecoration: "underline" }}
                >
                  <RouterLink
                    to="/recover-password"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Forgot your password?
                  </RouterLink>
                </Link>
              </Flex>
            }
            {...register("password", passwordRules())}
            placeholder="Password"
            errors={errors}
            size="md"
          />

          <Button
            variant="solid"
            colorPalette="teal"
            type="submit"
            loading={isSubmitting}
            size="md"
            w="full"
            mt={2}
          >
            Log In
          </Button>

          {hasOAuthProviders && <Separator my={2} />}

          {providers.google && (
            <Button
              variant="outline"
              size="md"
              onClick={handleGoogleLogin}
              type="button"
              w="full"
            >
              <FcGoogle />
              Sign in with Google
            </Button>
          )}

          {providers.keycloak && (
            <Button
              variant="outline"
              size="md"
              onClick={handleKeycloakLogin}
              type="button"
              w="full"
            >
              Sign in with Keycloak
            </Button>
          )}

          {providers.passkey && (
            <Button
              variant="outline"
              size="md"
              onClick={handlePasskeyLogin}
              type="button"
              w="full"
            >
              Sign in with a Passkey
            </Button>
          )}

          <Text fontSize="sm" color="gray.600" textAlign="center" mt={2}>
            Don't have an account yet?{" "}
            <Link asChild className="main-link" textDecoration="underline">
              <RouterLink to="/signup">Sign up</RouterLink>
            </Link>
          </Text>

          <Link
            as="a"
            href="https://github.com/thangphan205/tacacs-ng-ui"
            target="_blank"
            rel="noopener noreferrer"
            display="flex"
            alignItems="center"
            justifyContent="center"
            gap={1}
            color="gray.400"
            _hover={{ color: "gray.600" }}
            mt={6}
          >
            <Icon as={FiGithub} />
            <Text fontSize="xs" fontWeight="semibold">
              Version {version}
            </Text>
          </Link>
        </Box>
      </Flex>
    </Flex>
  )
}
