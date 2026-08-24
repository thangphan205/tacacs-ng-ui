import { Container, Heading, Tabs } from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import ApiKeys from "@/components/UserSettings/ApiKeys"
import Appearance from "@/components/UserSettings/Appearance"
import ChangePassword from "@/components/UserSettings/ChangePassword"
import PasskeyManager from "@/components/UserSettings/PasskeyManager"
import UserInformation from "@/components/UserSettings/UserInformation"
import useAuth from "@/hooks/useAuth"

const tabsConfig = [
  { value: "my-profile", title: "My profile", component: UserInformation },
  { value: "password", title: "Password", component: ChangePassword },
  { value: "security-keys", title: "Security Keys", component: PasskeyManager },
  { value: "appearance", title: "Appearance", component: Appearance },
]

// API keys are machine credentials for the MCP server; the routes behind this
// tab are superuser-only, so showing it to anyone else would only 403.
const superuserTabsConfig = [
  { value: "api-keys", title: "API Keys", component: ApiKeys },
]

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
})

function UserSettings() {
  const { user: currentUser } = useAuth()

  if (!currentUser) {
    return null
  }

  const tabs = currentUser.is_superuser
    ? [...tabsConfig, ...superuserTabsConfig]
    : tabsConfig

  return (
    <Container maxW="full">
      <Heading size="md" textAlign={{ base: "center", md: "left" }} py={12}>
        User Settings
      </Heading>

      <Tabs.Root defaultValue="my-profile" variant="subtle">
        <Tabs.List>
          {tabs.map((tab) => (
            <Tabs.Trigger key={tab.value} value={tab.value}>
              {tab.title}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {tabs.map((tab) => (
          <Tabs.Content key={tab.value} value={tab.value}>
            <tab.component />
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </Container>
  )
}
