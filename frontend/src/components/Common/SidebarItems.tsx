import { Box, Flex, Icon, Text } from "@chakra-ui/react"
import { Link as RouterLink, useMatchRoute } from "@tanstack/react-router"
import {
  FiActivity,
  FiAlertCircle,
  FiBell,
  FiBarChart2,
  FiCpu,
  FiDatabase,
  FiFileText,
  FiGitMerge,
  FiGrid,
  FiHome,
  FiList,
  FiSend,
  FiServer,
  FiSettings,
  FiShield,
  FiSliders,
  FiUser,
  FiUsers,
} from "react-icons/fi"
import type { IconType } from "react-icons/lib"
import { LuBoxes } from "react-icons/lu"
import useAuth from "@/hooks/useAuth"
import { Tooltip } from "../ui/tooltip"

interface NavItem {
  icon: IconType
  title: string
  path: string
  indent?: boolean
}

interface NavSection {
  label: string
  items: NavItem[]
}

const CONFIG_SECTIONS: NavSection[] = [
  {
    label: "Overview",
    items: [{ icon: FiHome, title: "Dashboard", path: "/" }],
  },
  {
    label: "TACACS+ Config",
    items: [
      { icon: LuBoxes, title: "TACACS Configs", path: "/tacacs_configs" },
      { icon: FiServer, title: "Hosts", path: "/hosts" },
      { icon: FiUsers, title: "Groups", path: "/tacacs_groups" },
      { icon: FiUser, title: "Users", path: "/tacacs_users" },
      { icon: FiGrid, title: "Services", path: "/tacacs_services" },
      { icon: FiFileText, title: "Profiles", path: "/profiles" },
      { icon: FiShield, title: "Rulesets", path: "/rulesets" },
      { icon: FiDatabase, title: "MAVIS", path: "/mavises" },
      {
        icon: FiSliders,
        title: "Config Options",
        path: "/configuration_options",
      },
      { icon: FiSettings, title: "NG Settings", path: "/tacacs_ng_settings" },
    ],
  },
  {
    label: "Monitoring",
    items: [
      { icon: FiList, title: "TACACS Logs", path: "/tacacs_logs" },
      { icon: FiBell, title: "Alert Rules", path: "/alert_rules" },
      {
        icon: FiSend,
        title: "Notification Channels",
        path: "/notification_channels",
      },
      { icon: FiAlertCircle, title: "Alert Events", path: "/alert_events" },
      { icon: FiCpu, title: "Anomaly Detection", path: "/anomaly_detection" },
      { icon: FiActivity, title: "Audit Logs", path: "/audit_logs" },
      {
        icon: FiBarChart2,
        title: "AAA Statistics",
        path: "/aaa_statistics",
      },
      {
        icon: FiBarChart2,
        title: "AAA Range Stats",
        path: "/aaa_statistics_range",
        indent: true,
      },
      {
        icon: FiBarChart2,
        title: "Node Comparison",
        path: "/aaa_statistics_nodes",
        indent: true,
      },
      {
        icon: FiGitMerge,
        title: "High Availability",
        path: "/high_availability",
      },
    ],
  },
]

const ADMIN_SECTION: NavSection = {
  label: "Admin",
  items: [
    {
      icon: FiUsers,
      title: "Users Management",
      path: "/admin/users_management",
    },
    { icon: FiShield, title: "Auth Providers", path: "/admin/auth-providers" },
  ],
}

interface SidebarNavItemProps extends NavItem {
  onClose?: () => void
  isCollapsed?: boolean
}

function SidebarNavItem({
  icon,
  title,
  path,
  indent,
  onClose,
  isCollapsed,
}: SidebarNavItemProps) {
  const matchRoute = useMatchRoute()
  const isActive = !!matchRoute({ to: path as never, fuzzy: path !== "/" })

  return (
    <Tooltip content={title} placement="right" disabled={!isCollapsed}>
      <RouterLink to={path as never} onClick={onClose}>
        <Flex
          align="center"
          gap={3}
          pl={isCollapsed ? 0 : indent ? 8 : 4}
          pr={isCollapsed ? 0 : 4}
          py={2.5}
          mx={2}
          my={0.5}
          borderRadius="xl"
          position="relative"
          bg={isActive ? "teal.50" : "transparent"}
          _dark={{ bg: isActive ? "rgba(0,150,136,0.12)" : "transparent" }}
          _hover={{
            bg: isActive ? "teal.50" : "gray.100",
            transform: "translateX(2px)",
            _dark: {
              bg: isActive ? "rgba(0,150,136,0.12)" : "whiteAlpha.50",
            },
          }}
          color={isActive ? "teal.700" : "fg.muted"}
          fontWeight={isActive ? "bold" : "medium"}
          fontSize="sm"
          transition="all 0.2s cubic-bezier(0.4, 0, 0.2, 1)"
          cursor="pointer"
          justify={isCollapsed ? "center" : "flex-start"}
        >
          {/* Active indicator bar */}
          {isActive && (
            <Box
              position="absolute"
              left={0}
              top="25%"
              height="50%"
              width="3px"
              bg="teal.600"
              borderRadius="full"
            />
          )}
          <Icon
            as={icon}
            flexShrink={0}
            fontSize={!isCollapsed && indent ? "xs" : "md"}
            color={isActive ? "teal.600" : "fg.muted"}
          />
          {!isCollapsed && <Text lineClamp={1}>{title}</Text>}
        </Flex>
      </RouterLink>
    </Tooltip>
  )
}

function SectionLabel({
  label,
  isCollapsed,
}: {
  label: string
  isCollapsed?: boolean
}) {
  if (isCollapsed) {
    return (
      <Flex justify="center" align="center" my={2}>
        <Box
          w="6px"
          h="6px"
          borderRadius="full"
          bg="border.subtle"
          opacity={0.6}
        />
      </Flex>
    )
  }

  return (
    <Text
      fontSize="2xs"
      fontWeight="extrabold"
      color="fg.subtle"
      textTransform="uppercase"
      letterSpacing="widest"
      px={4}
      pt={4}
      pb={1.5}
      opacity={0.7}
    >
      {label}
    </Text>
  )
}

interface SidebarItemsProps {
  onClose?: () => void
  isCollapsed?: boolean
}

const SidebarItems = ({ onClose, isCollapsed }: SidebarItemsProps) => {
  const { user: currentUser } = useAuth()

  const sections = currentUser?.is_superuser
    ? [...CONFIG_SECTIONS, ADMIN_SECTION]
    : CONFIG_SECTIONS

  return (
    <Box py={2}>
      {sections.map((section) => (
        <Box key={section.label}>
          <SectionLabel label={section.label} isCollapsed={isCollapsed} />
          {section.items.map((item) => (
            <SidebarNavItem
              key={item.path}
              {...item}
              onClose={onClose}
              isCollapsed={isCollapsed}
            />
          ))}
        </Box>
      ))}
    </Box>
  )
}

export default SidebarItems
