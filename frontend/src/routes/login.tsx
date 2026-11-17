import {
  Box,
  Flex,
  Icon,
  Image,
  Input,
  Link,
  Separator,
  Tabs,
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
import { FaMicrosoft } from "react-icons/fa"
import { FcGoogle } from "react-icons/fc"
import { FiGithub } from "react-icons/fi"
import { apiBaseUrl } from "@/api"
import type { BodyLoginLoginAccessToken as AccessToken } from "@/client"
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
  ldap: boolean
  microsoft: boolean
  passkey: boolean
  password_login: boolean
  open_registration: boolean
}

type LoginMethod = "ldap" | "local"

// Remembers which tab this browser used last; LDAP otherwise.
const LOGIN_TAB_KEY = "login_tab"

function readSavedTab(): LoginMethod {
  try {
    return localStorage.getItem(LOGIN_TAB_KEY) === "local" ? "local" : "ldap"
  } catch {
    return "ldap"
  }
}

interface CredentialsFormProps {
  method: LoginMethod
  onSubmit: (data: AccessToken) => Promise<unknown>
  error: string | null
}

/** One sign-in form: local (email) or LDAP (directory username). */
function CredentialsForm({ method, onSubmit, error }: CredentialsFormProps) {
  const isLocal = method === "local"
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AccessToken>({
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { username: "", password: "" },
  })

  const submit: SubmitHandler<AccessToken> = async (data) => {
    if (isSubmitting) return
    try {
      await onSubmit(data)
    } catch {
      // error is handled by useAuth hook
    }
  }

  return (
    <Box
      as="form"
      onSubmit={handleSubmit(submit)}
      display="flex"
      flexDirection="column"
      gap={5}
    >
      {!isLocal && (
        <Text fontSize="sm" color="fg.muted">
          Use your directory (LDAP / Active Directory) account.
        </Text>
      )}

      <Field
        label={isLocal ? "Email" : "Username"}
        invalid={!!errors.username}
        errorText={errors.username?.message || !!error}
      >
        <Input
          {...register("username", {
            required: "Username is required",
            ...(isLocal ? { pattern: emailPattern } : {}),
          })}
          placeholder={isLocal ? "Email" : "Username"}
          type={isLocal ? "email" : "text"}
          autoComplete="username"
          size="md"
        />
      </Field>

      <PasswordInput
        type="password"
        label={
          isLocal ? (
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
                  Forgot password?
                </RouterLink>
              </Link>
            </Flex>
          ) : (
            "Password"
          )
        }
        // Directory passwords follow the directory's policy, not ours.
        {...register(
          "password",
          isLocal ? passwordRules() : { required: "Password is required" },
        )}
        placeholder="Password"
        autoComplete="current-password"
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
    </Box>
  )
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
  const { loginMutation, ldapLoginMutation, error, resetError } = useAuth()
  const navigate = useNavigate()
  const [providers, setProviders] = useState<ProvidersStatus>({
    google: false,
    keycloak: false,
    ldap: false,
    microsoft: false,
    passkey: false,
    // Shown until the status says otherwise, as before LDAP existed.
    password_login: true,
    open_registration: false,
  })
  const [tab, setTab] = useState<LoginMethod>(readSavedTab)

  useEffect(() => {
    fetch(`${apiBaseUrl()}/api/v1/auth-providers/status`)
      .then((r) => r.json())
      .then((data: ProvidersStatus) => setProviders(data))
      .catch(() => {})
  }, [])

  const handleGoogleLogin = async () => {
    try {
      const res = await fetch(`${apiBaseUrl()}/api/v1/oauth/google/authorize`)
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
      const res = await fetch(`${apiBaseUrl()}/api/v1/oauth/keycloak/authorize`)
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

  const handleMicrosoftLogin = async () => {
    try {
      const res = await fetch(
        `${apiBaseUrl()}/api/v1/oauth/microsoft/authorize`,
      )
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
        `${apiBaseUrl()}/api/v1/passkeys/authenticate/begin`,
        {
          method: "POST",
        },
      )
      if (!beginRes.ok)
        throw new Error("Failed to begin passkey authentication")
      const options = await beginRes.json()

      const credential = await startAuthentication({ optionsJSON: options })

      const completeRes = await fetch(
        `${apiBaseUrl()}/api/v1/passkeys/authenticate/complete`,
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

  const changeTab = (value: LoginMethod) => {
    setTab(value)
    resetError()
    try {
      localStorage.setItem(LOGIN_TAB_KEY, value)
    } catch {
      // private mode / blocked storage: the tab just isn't remembered
    }
  }

  const showLocal = providers.password_login
  const showLdap = providers.ldap

  const localForm = (
    <CredentialsForm
      method="local"
      error={error}
      onSubmit={(data) => {
        resetError()
        return loginMutation.mutateAsync(data)
      }}
    />
  )
  const ldapForm = (
    <CredentialsForm
      method="ldap"
      error={error}
      onSubmit={(data) => {
        resetError()
        return ldapLoginMutation.mutateAsync(data)
      }}
    />
  )

  const hasOAuthProviders =
    providers.google ||
    providers.keycloak ||
    providers.microsoft ||
    providers.passkey

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
        <Box w="full" maxW="sm" display="flex" flexDirection="column" gap={5}>
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

          {showLocal && showLdap ? (
            <Tabs.Root
              value={tab}
              onValueChange={(e) => changeTab(e.value as LoginMethod)}
              variant="line"
              fitted
            >
              <Tabs.List>
                <Tabs.Trigger value="ldap">LDAP</Tabs.Trigger>
                <Tabs.Trigger value="local">Local Account</Tabs.Trigger>
              </Tabs.List>
              <Tabs.Content value="ldap" pt={5}>
                {ldapForm}
              </Tabs.Content>
              <Tabs.Content value="local" pt={5}>
                {localForm}
              </Tabs.Content>
            </Tabs.Root>
          ) : showLdap ? (
            ldapForm
          ) : showLocal ? (
            localForm
          ) : null}

          {hasOAuthProviders && (showLocal || showLdap) && <Separator my={2} />}

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

          {providers.microsoft && (
            <Button
              variant="outline"
              size="md"
              onClick={handleMicrosoftLogin}
              type="button"
              w="full"
            >
              <FaMicrosoft />
              Sign in with Microsoft
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

          {providers.open_registration && (
            <Text fontSize="sm" color="gray.600" textAlign="center" mt={2}>
              Don't have an account yet?{" "}
              <Link asChild className="main-link" textDecoration="underline">
                <RouterLink to="/signup">Sign up</RouterLink>
              </Link>
            </Text>
          )}

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
              {__BUILD_INFO__ && ` (${__BUILD_INFO__})`}
            </Text>
          </Link>
        </Box>
      </Flex>
    </Flex>
  )
}
