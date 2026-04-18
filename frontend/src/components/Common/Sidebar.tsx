import { Box, Flex, Icon, IconButton, Link, Text, VStack } from "@chakra-ui/react"
import { useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { FaBars } from "react-icons/fa"
import { FiGithub, FiLogOut } from "react-icons/fi"

import type { UserPublic } from "@/client"
import useAuth from "@/hooks/useAuth"
import { version } from "../../../package.json"
import {
  DrawerBackdrop,
  DrawerBody,
  DrawerCloseTrigger,
  DrawerContent,
  DrawerRoot,
  DrawerTrigger,
} from "../ui/drawer"
import SidebarItems from "./SidebarItems"

const VersionLink = () => (
  <Link
    href="https://github.com/thangphan205/tacacs-ng-ui"
    target="_blank"
    rel="noopener noreferrer"
    display="flex"
    alignItems="center"
    gap={2}
  >
    <Icon as={FiGithub} />
    <Text fontSize="sm" fontWeight="bold">Version {version}</Text>
  </Link>
)

const Sidebar = () => {
  const queryClient = useQueryClient()
  const currentUser = queryClient.getQueryData<UserPublic>(["currentUser"])
  const { logout } = useAuth()
  const [open, setOpen] = useState(false)

  return (
    <>
      {/* Mobile */}
      <DrawerRoot
        placement="start"
        open={open}
        onOpenChange={(e) => setOpen(e.open)}
      >
        <DrawerBackdrop />
        <DrawerTrigger asChild>
          <IconButton
            variant="ghost"
            color="inherit"
            display={{ base: "flex", md: "none" }}
            aria-label="Open Menu"
            position="absolute"
            zIndex="100"
            m={4}
          >
            <FaBars />
          </IconButton>
        </DrawerTrigger>
        <DrawerContent maxW="xs">
          <DrawerCloseTrigger />
          <DrawerBody>
            <Flex flexDir="column" justify="space-between" h="full">
              <Box>
                <SidebarItems onClose={() => setOpen(false)} />
                <Flex
                  as="button"
                  onClick={logout}
                  alignItems="center"
                  gap={4}
                  px={4}
                  py={2}
                >
                  <FiLogOut />
                  <Text>Log Out</Text>
                </Flex>
              </Box>
              <VStack align="start" p={2} gap={2}>
                <VersionLink />
                {currentUser?.email && (
                  <Text fontSize="sm" truncate maxW="full">
                    Logged in as: {currentUser.email}
                  </Text>
                )}
              </VStack>
            </Flex>
          </DrawerBody>
          <DrawerCloseTrigger />
        </DrawerContent>
      </DrawerRoot>

      {/* Desktop */}
      <Flex
        display={{ base: "none", md: "flex" }}
        direction="column"
        bg="bg.subtle"
        minW="xs"
        h="full"
        p={4}
      >
        <Box overflowY="auto" flex="1" minH={0}>
          <SidebarItems />
        </Box>
        <VStack align="start" pt={4} gap={2}>
          <VersionLink />
          {currentUser?.email && (
            <Text fontSize="sm">Logged in as: {currentUser.email}</Text>
          )}
        </VStack>
      </Flex>
    </>
  )
}

export default Sidebar
