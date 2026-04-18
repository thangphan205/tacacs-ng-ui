import { Alert, Button, HStack, Input, Text, VStack } from "@chakra-ui/react"
import { startRegistration } from "@simplewebauthn/browser"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { OpenAPI } from "@/client"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTitle,
} from "@/components/ui/dialog"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

function authHeader() {
  return { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
}

async function fetchPasskeys(): Promise<{ data: unknown[]; count: number }> {
  const res = await fetch(`${OpenAPI.BASE}/api/v1/passkeys/`, { headers: authHeader() })
  if (!res.ok) throw new Error("Failed to load passkeys")
  return res.json()
}

async function beginRegistration() {
  const res = await fetch(`${OpenAPI.BASE}/api/v1/passkeys/register/begin`, {
    method: "POST",
    headers: authHeader(),
  })
  if (!res.ok) throw new Error("Failed to begin registration")
  return res.json()
}

async function completeRegistration(credential: unknown, name: string | null) {
  const res = await fetch(`${OpenAPI.BASE}/api/v1/passkeys/register/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({ credential, name }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail ?? "Registration failed")
  }
  return res.json()
}

async function disablePasswordLogin() {
  const res = await fetch(`${OpenAPI.BASE}/api/v1/users/me`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({ password_login_disabled: true }),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail ?? "Failed to update setting")
  }
  return res.json()
}

// ── Registration dialog ─────────────────────────────────────────────────────

interface RegisterDialogProps {
  open: boolean
  onClose: () => void
}

function RegisterDialog({ open, onClose }: RegisterDialogProps) {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const [passkeyName, setPasskeyName] = useState("")
  const [isRegistering, setIsRegistering] = useState(false)
  const [registered, setRegistered] = useState(false)

  const registerMutation = useMutation({
    mutationFn: async () => {
      setIsRegistering(true)
      try {
        const options = await beginRegistration()
        const credential = await startRegistration({ optionsJSON: options })
        await completeRegistration(credential, passkeyName.trim() || null)
      } finally {
        setIsRegistering(false)
      }
    },
    onSuccess: () => {
      showSuccessToast("Passkey registered successfully.")
      queryClient.invalidateQueries({ queryKey: ["passkeys"] })
      setRegistered(true)
    },
    onError: (err: Error) => {
      if (err.name === "NotAllowedError") return
      handleError(err as never)
    },
  })

  const disableMutation = useMutation({
    mutationFn: disablePasswordLogin,
    onSuccess: () => {
      showSuccessToast("Password login disabled for your account.")
      queryClient.invalidateQueries({ queryKey: ["currentUser"] })
      onClose()
    },
    onError: (err: Error) => handleError(err as never),
  })

  function handleClose() {
    setRegistered(false)
    setPasskeyName("")
    onClose()
  }

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      open={open}
      onOpenChange={({ open: o }) => { if (!o) handleClose() }}
    >
      <DialogContent>
        <DialogCloseTrigger />
        <DialogHeader>
          <DialogTitle>
            {registered ? "Passkey Registered!" : "Register a passkey"}
          </DialogTitle>
        </DialogHeader>
        <DialogBody>
          {registered ? (
            <VStack align="start" gap={3}>
              <Text>
                Your passkey has been saved. You can now sign in without a password.
              </Text>
              <Text color="fg.muted">
                Would you like to disable password login for your account? You will
                only be able to sign in using your passkey.
              </Text>
            </VStack>
          ) : (
            <VStack align="start" gap={3}>
              <Text>
                Passkeys let you sign in with your device's biometrics or PIN — no
                password required.
              </Text>
              <Input
                placeholder="Key name (optional, e.g. My MacBook)"
                value={passkeyName}
                onChange={(e) => setPasskeyName(e.target.value)}
                size="sm"
              />
            </VStack>
          )}
        </DialogBody>
        <DialogFooter>
          {registered ? (
            <HStack gap={3}>
              <Button variant="outline" onClick={handleClose}>
                No thanks
              </Button>
              <Button
                colorPalette="red"
                loading={disableMutation.isPending}
                onClick={() => disableMutation.mutate()}
              >
                Disable password login
              </Button>
            </HStack>
          ) : (
            <HStack gap={3}>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                colorPalette="blue"
                loading={isRegistering || registerMutation.isPending}
                onClick={() => registerMutation.mutate()}
              >
                Register Passkey
              </Button>
            </HStack>
          )}
        </DialogFooter>
      </DialogContent>
    </DialogRoot>
  )
}

// ── Top-of-page banner ──────────────────────────────────────────────────────

const PasskeyPromptModal = () => {
  const { user: currentUser } = useAuth()
  const [dialogOpen, setDialogOpen] = useState(false)

  const { data: passkeysData, isSuccess: passkeysLoaded } = useQuery({
    queryKey: ["passkeys"],
    queryFn: fetchPasskeys,
    enabled: !!currentUser,
  })

  if (!passkeysLoaded || (passkeysData?.count ?? 0) > 0) return null

  return (
    <>
      <Alert.Root status="info" mb={4} borderRadius="md">
        <Alert.Indicator />
        <Alert.Content>
          <Alert.Title>Improve your account security</Alert.Title>
          <Alert.Description>
            You haven't set up a passkey yet. Passkeys let you sign in with your
            device's biometrics or PIN — faster and more secure than a password.
          </Alert.Description>
        </Alert.Content>
        <Button
          size="sm"
          colorPalette="blue"
          flexShrink={0}
          ml="auto"
          onClick={() => setDialogOpen(true)}
        >
          Register passkey
        </Button>
      </Alert.Root>

      <RegisterDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
      />
    </>
  )
}

export default PasskeyPromptModal
