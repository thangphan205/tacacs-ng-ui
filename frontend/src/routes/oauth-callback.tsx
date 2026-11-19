import { Spinner } from "@chakra-ui/react"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect } from "react"
import { z } from "zod"

const searchSchema = z.object({
  token: z.string().optional(),
  error: z.string().optional(),
})

export const Route = createFileRoute("/oauth-callback")({
  validateSearch: searchSchema,
  component: OAuthCallback,
})

function OAuthCallback() {
  const { token, error } = Route.useSearch()
  const navigate = useNavigate()

  useEffect(() => {
    if (token) {
      localStorage.setItem("access_token", token)
      navigate({ to: "/" })
    } else if (error) {
      navigate({ to: "/login", search: { error } })
    } else {
      navigate({ to: "/login" })
    }
  }, [token, error, navigate])

  return <Spinner size="xl" mt="20vh" display="block" mx="auto" />
}
