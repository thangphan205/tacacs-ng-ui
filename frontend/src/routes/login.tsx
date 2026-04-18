import { Container, Icon, Image, Input, Link, Separator, Text } from "@chakra-ui/react"
import { startAuthentication } from "@simplewebauthn/browser"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
  useNavigate,
} from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { type SubmitHandler, useForm } from "react-hook-form"
import { FiGithub, FiLock, FiMail } from "react-icons/fi"
import { FcGoogle } from "react-icons/fc"

import type { Body_login_login_access_token as AccessToken } from "@/client"
import { OpenAPI } from "@/client"
import { Button } from "@/components/ui/button"
import { Field } from "@/components/ui/field"
import { InputGroup } from "@/components/ui/input-group"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"
import { handleError } from "@/utils"
import Logo from "/assets/images/tacacs-ng-ui.svg"
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
      handleError({ status: 0, body: { detail: "Could not reach the server." } } as never)
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
      handleError({ status: 0, body: { detail: "Could not reach the server." } } as never)
    }
  }

  const handlePasskeyLogin = async () => {
    try {
      const beginRes = await fetch(`${OpenAPI.BASE}/api/v1/passkeys/authenticate/begin`, {
        method: "POST",
      })
      if (!beginRes.ok) throw new Error("Failed to begin passkey authentication")
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
      handleError({ status: 0, body: { detail: (err as Error).message } } as never)
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

  const hasOAuthProviders = providers.google || providers.keycloak || providers.passkey

  return (
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
        invalid={!!errors.username}
        errorText={errors.username?.message || !!error}
      >
        <InputGroup w="100%" startElement={<FiMail />}>
          <Input
            {...register("username", {
              required: "Username is required",
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
        {...register("password", passwordRules())}
        placeholder="Password"
        errors={errors}
      />
      <RouterLink to="/recover-password" className="main-link">
        Forgot Password?
      </RouterLink>
      <Button variant="solid" type="submit" loading={isSubmitting} size="md">
        Log In
      </Button>

      {hasOAuthProviders && <Separator />}

      {providers.google && (
        <Button variant="outline" size="md" onClick={handleGoogleLogin} type="button">
          <FcGoogle />
          Sign in with Google
        </Button>
      )}

      {providers.keycloak && (
        <Button variant="outline" size="md" onClick={handleKeycloakLogin} type="button">
          Sign in with Keycloak
        </Button>
      )}

      {providers.passkey && (
        <Button variant="outline" size="md" onClick={handlePasskeyLogin} type="button">
          Sign in with a Passkey
        </Button>
      )}

      <Text>
        Don't have an account?{" "}
        <RouterLink to="/signup" className="main-link">
          Sign Up
        </RouterLink>
      </Text>
      <Link
        as="a"
        href="https://github.com/thangphan205/tacacs-ng-ui"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icon as={FiGithub} />
        <Text fontSize="sm" fontWeight="bold">Version {version}</Text>
      </Link>
    </Container>
  )
}
