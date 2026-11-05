import { Alert, Code, List } from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"

import { TacacsConfigsService } from "@/client"

export const defaultCredentialsQueryKey = [
  "tacacs_configs",
  "default_credentials",
]

const DEMO_SECRET = "change_this"

interface DefaultCredentialsAlertProps {
  mt?: number
  mb?: number
}

/**
 * Warns while a TACACS+ user or host in the generated config still uses the
 * public demo secret. The demo data is seeded once with a password printed in
 * the README; anything still carrying it is a login anyone can use on every
 * device that points at this server.
 */
export function DefaultCredentialsAlert({
  mt,
  mb,
}: DefaultCredentialsAlertProps) {
  const { data } = useQuery({
    queryKey: defaultCredentialsQueryKey,
    queryFn: () => TacacsConfigsService.readDefaultCredentials(),
  })

  if (!data || data.count === 0) return null

  return (
    <Alert.Root status="error" mt={mt} mb={mb} borderRadius="md">
      <Alert.Indicator />
      <Alert.Content>
        <Alert.Title>Default demo credentials in use</Alert.Title>
        <Alert.Description>
          These entries use the public demo secret <Code>{DEMO_SECRET}</Code>.
          Change the password or key, or delete the entry, then generate and
          activate a new configuration.
          <List.Root mt={2} ps={4}>
            {data.data.map((finding) => (
              <List.Item key={`${finding.kind}-${finding.id}`}>
                {finding.kind === "host" ? "Host" : "TACACS user"}{" "}
                <Code>{finding.name}</Code>
                {finding.kind === "host"
                  ? " — shared key"
                  : " — login password"}
              </List.Item>
            ))}
          </List.Root>
        </Alert.Description>
      </Alert.Content>
    </Alert.Root>
  )
}
