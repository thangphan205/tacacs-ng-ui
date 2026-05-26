import { Flex } from "@chakra-ui/react"
import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"

import PasskeyPromptModal from "@/components/Common/PasskeyPromptModal"
import Sidebar from "@/components/Common/Sidebar"
import { isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  return (
    <Flex h="100vh" direction={{ base: "column", md: "row" }} overflow="hidden">
      <Sidebar />
      <Flex flex="1" direction="column" p={4} overflowY="auto">
        <PasskeyPromptModal />
        <Outlet />
      </Flex>
    </Flex>
  )
}

export default Layout
