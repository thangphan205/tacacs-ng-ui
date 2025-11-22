import { Box, Flex, Icon, Text } from "@chakra-ui/react"
import { useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import {
  FiArchive,
  FiCode,
  FiDatabase,
  FiFileText,
  FiGrid,
  FiHome,
  FiLayers,
  FiList,
  FiSettings,
  FiServer,
  FiShield,
  FiUser,
  FiUsers,
} from "react-icons/fi"
import type { IconType } from "react-icons/lib"

import type { UserPublic } from "@/client"

const items = [
  { icon: FiHome, title: "Dashboard", path: "/", level: 1 },
  { icon: FiArchive, title: "Tacacs configs", path: "/tacacs_configs", level: 1 },
  { icon: FiServer, title: "Hosts", path: "/hosts", level: 1 },
  { icon: FiUsers, title: "Tacacs Groups", path: "/tacacs_groups", level: 1 },
  { icon: FiUser, title: "Tacacs Users", path: "/tacacs_users", level: 1 },
  { icon: FiGrid, title: "Tacacs Services", path: "/tacacs_services", level: 1 },
  { icon: FiFileText, title: "Profiles", path: "/profiles", level: 1 },
  { icon: FiCode, title: "Profiles Script", path: "/profilescripts", level: 2 },
  { icon: FiLayers, title: "Profiles Script Set", path: "/profilescriptsets", level: 2 },
  { icon: FiShield, title: "Rulesets", path: "/rulesets", level: 1 },
  { icon: FiCode, title: "Rulesets Script", path: "/rulesetscripts", level: 2 },
  { icon: FiLayers, title: "Rulesets Script Set", path: "/rulesetscriptsets", level: 2 },
  {
    icon: FiSettings,
    title: "Tacacs-ng Settings",
    path: "/tacacs_ng_settings",
    level: 1,
  },
  { icon: FiDatabase, title: "Mavis Settings", path: "/mavis_settings", level: 1 },
  { icon: FiList, title: "Tacacs logs", path: "/tacacs_logs", level: 1 },
  { icon: FiSettings, title: "User Settings", path: "/settings", level: 1 },
]

interface SidebarItemsProps {
  onClose?: () => void
}

interface Item {
  icon: IconType
  title: string
  path: string
  level: number
}

const SidebarItems = ({ onClose }: SidebarItemsProps) => {
  const queryClient = useQueryClient()
  const currentUser = queryClient.getQueryData<UserPublic>(["currentUser"])

  const finalItems: Item[] = currentUser?.is_superuser
    ? [...items, { icon: FiUsers, title: "Admin", path: "/admin", level: 1 }]
    : items

  const listItems = finalItems.map(({ icon, title, path, level }) => (
    <RouterLink key={title} to={path} onClick={onClose}>
      <Flex
        gap={4}
        px={level === 1 ? 4 : 8}
        py={2}
        _hover={{
          background: "gray.subtle",
        }}
        alignItems="center"
        fontSize="sm"
      >
        <Icon as={icon} alignSelf="center" />
        <Text ml={2}>{title}</Text>
      </Flex>
    </RouterLink>
  ))

  return (
    <>
      <Text fontSize="xs" px={4} py={2} fontWeight="bold">
        Menu
      </Text>
      <Box>{listItems}</Box>
    </>
  )
}

export default SidebarItems
