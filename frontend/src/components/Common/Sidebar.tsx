import {
  Box,
  Flex,
  Icon,
  IconButton,
  Image,
  Link,
  Text,
  VStack,
} from "@chakra-ui/react"
import { Link as RouterLink } from "@tanstack/react-router"
import { useState } from "react"
import { FaBars } from "react-icons/fa"
import {
  FiChevronLeft,
  FiChevronRight,
  FiGithub,
  FiLogOut,
  FiSettings,
} from "react-icons/fi"
import useAuth from "@/hooks/useAuth"
import Logo from "/assets/images/tacacs-ng-ui-logo.svg"
import { version } from "../../../package.json"
import {
  DrawerBackdrop,
  DrawerBody,
  DrawerCloseTrigger,
  DrawerContent,
  DrawerRoot,
} from "../ui/drawer"
import { Tooltip } from "../ui/tooltip"
import SidebarItems from "./SidebarItems"

const SidebarFooter = ({
  email,
  onClose,
  isCollapsed,
}: {
  email?: string
  onClose?: () => void
  isCollapsed?: boolean
}) => {
  const { logout } = useAuth()

  return (
    <VStack
      align="stretch"
      pt={4}
      pb={2}
      px={isCollapsed ? 1 : 3}
      gap={2}
      borderTopWidth="1px"
      borderTopColor="border.muted"
    >
      {/* Profile Card */}
      {!isCollapsed ? (
        <Flex
          align="center"
          gap={3}
          p={2.5}
          borderRadius="xl"
          bg="bg.muted"
          borderWidth="1px"
          borderColor="border.subtle"
        >
          {/* Avatar Initial Circle */}
          <Flex
            align="center"
            justify="center"
            boxSize="8"
            borderRadius="full"
            bg="teal.600"
            color="white"
            fontWeight="bold"
            fontSize="sm"
            flexShrink={0}
          >
            {email ? email.substring(0, 2).toUpperCase() : "U"}
          </Flex>
          <VStack align="flex-start" gap={0} flex="1" overflow="hidden">
            <Text
              fontSize="sm"
              fontWeight="bold"
              truncate
              maxW="100%"
              color="fg.default"
            >
              {email ? email.split("@")[0] : "User"}
            </Text>
            <Text fontSize="xs" color="fg.subtle" truncate maxW="100%">
              {email || "user@example.com"}
            </Text>
          </VStack>
        </Flex>
      ) : (
        <Tooltip content={email || "User"} placement="right">
          <Flex
            align="center"
            justify="center"
            boxSize="10"
            borderRadius="full"
            bg="teal.600"
            color="white"
            fontWeight="bold"
            fontSize="md"
            mx="auto"
            cursor="pointer"
          >
            {email ? email.substring(0, 2).toUpperCase() : "U"}
          </Flex>
        </Tooltip>
      )}

      {/* Action Links */}
      <VStack align="stretch" gap={1}>
        <Tooltip
          content="User Settings"
          placement="right"
          disabled={!isCollapsed}
        >
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <RouterLink to={"/settings" as any} onClick={onClose}>
            <Flex
              align="center"
              gap={3}
              px={3}
              py={2}
              borderRadius="lg"
              fontSize="sm"
              fontWeight="medium"
              color="fg.muted"
              _hover={{ bg: "gray.subtle", color: "teal.600" }}
              cursor="pointer"
              transition="all 0.15s"
              justify={isCollapsed ? "center" : "flex-start"}
            >
              <Icon as={FiSettings} />
              {!isCollapsed && <Text>Settings</Text>}
            </Flex>
          </RouterLink>
        </Tooltip>

        <Tooltip content="Log Out" placement="right" disabled={!isCollapsed}>
          <Flex
            as="button"
            align="center"
            gap={3}
            px={3}
            py={2}
            borderRadius="lg"
            fontSize="sm"
            fontWeight="medium"
            color="fg.muted"
            _hover={{ bg: "red.subtle", color: "red.600" }}
            transition="all 0.15s"
            onClick={logout}
            w="full"
            justify={isCollapsed ? "center" : "flex-start"}
          >
            <Icon as={FiLogOut} />
            {!isCollapsed && <Text>Log Out</Text>}
          </Flex>
        </Tooltip>
      </VStack>

      {/* GitHub & Version Info */}
      <Flex align="center" justify="center" gap={1.5} pt={2} color="fg.subtle">
        <Link
          href="https://github.com/thangphan205/tacacs-ng-ui"
          target="_blank"
          rel="noopener noreferrer"
          display="flex"
          alignItems="center"
          gap={1.5}
          fontSize="3xs"
          _hover={{ color: "fg.muted" }}
        >
          <Icon as={FiGithub} />
          {!isCollapsed && <Text>v{version}</Text>}
        </Link>
      </Flex>
    </VStack>
  )
}

const Sidebar = () => {
  const { user: currentUser } = useAuth()
  const [open, setOpen] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(
    () => localStorage.getItem("sidebar-collapsed") === "true",
  )

  const toggleCollapsed = () => {
    const next = !isCollapsed
    setIsCollapsed(next)
    localStorage.setItem("sidebar-collapsed", String(next))
  }

  return (
    <>
      {/* Mobile: top bar */}
      <Flex
        display={{ base: "flex", md: "none" }}
        align="center"
        gap={3}
        px={4}
        py={2}
        bg="bg.muted"
        borderBottomWidth="1px"
        w="full"
        flexShrink={0}
      >
        <IconButton
          variant="ghost"
          color="inherit"
          size="sm"
          aria-label="Open Menu"
          onClick={() => setOpen(true)}
        >
          <FaBars />
        </IconButton>
        <Image src={Logo} alt="Logo" boxSize={6} />
        <Text fontWeight="bold" fontSize="md">
          TACACS-NG-UI
        </Text>
      </Flex>

      {/* Mobile: drawer (state controlled directly, no DrawerTrigger needed) */}
      <DrawerRoot
        placement="start"
        open={open}
        onOpenChange={(e) => setOpen(e.open)}
      >
        <DrawerBackdrop />
        <DrawerContent maxW="xs">
          <DrawerCloseTrigger />
          <DrawerBody px={2} py={0}>
            <Flex flexDir="column" justify="space-between" h="full" pb={4}>
              <Box overflowY="auto" flex="1" minH={0}>
                <SidebarItems onClose={() => setOpen(false)} />
              </Box>
              <SidebarFooter
                email={currentUser?.email}
                onClose={() => setOpen(false)}
              />
            </Flex>
          </DrawerBody>
        </DrawerContent>
      </DrawerRoot>

      {/* Desktop: collapsible sidebar */}
      <Flex
        display={{ base: "none", md: "flex" }}
        direction="column"
        bg="bg.subtle"
        w={isCollapsed ? "14" : "60"}
        minW={isCollapsed ? "14" : "60"}
        h="full"
        py={2}
        borderRightWidth="1px"
        transition="width 0.2s ease, min-width 0.2s ease"
        overflow="hidden"
        flexShrink={0}
      >
        {/* Logo header */}
        <Flex
          align="center"
          gap={3}
          px={isCollapsed ? 0 : 4}
          py={4}
          mb={2}
          flexShrink={0}
          justify="center"
        >
          <Image
            src={Logo}
            alt="Logo"
            boxSize="8"
            flexShrink={0}
            transition="transform 0.3s ease"
            _hover={{ transform: "rotate(10deg) scale(1.15)" }}
          />
          {!isCollapsed && (
            <Text
              fontWeight="extrabold"
              fontSize="lg"
              flex="1"
              truncate
              bgGradient="to-r"
              gradientFrom="teal.600"
              gradientTo="cyan.500"
              bgClip="text"
              _dark={{
                gradientFrom: "teal.400",
                gradientTo: "cyan.300",
              }}
              letterSpacing="tight"
            >
              TACACS-NG-UI
            </Text>
          )}
        </Flex>

        {/* Nav items */}
        <Box overflowY="auto" flex="1" minH={0}>
          <SidebarItems isCollapsed={isCollapsed} />
        </Box>

        {/* Collapse toggle */}
        <Flex justify={isCollapsed ? "center" : "flex-end"} px={2} py={1}>
          <IconButton
            size="xs"
            variant="ghost"
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={toggleCollapsed}
          >
            {isCollapsed ? <FiChevronRight /> : <FiChevronLeft />}
          </IconButton>
        </Flex>

        {/* Footer */}
        <SidebarFooter email={currentUser?.email} isCollapsed={isCollapsed} />
      </Flex>
    </>
  )
}

export default Sidebar
