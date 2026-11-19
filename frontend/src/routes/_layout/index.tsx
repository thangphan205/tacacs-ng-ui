import {
  Badge,
  Box,
  Button,
  Container,
  Flex,
  Grid,
  GridItem,
  Heading,
  HStack,
  IconButton,
  Input,
  Skeleton,
  Spinner,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { useState } from "react"
import type { IconType } from "react-icons"
import {
  FiActivity,
  FiArrowRight,
  FiClock,
  FiFileText,
  FiFolder,
  FiGlobe,
  FiInbox,
  FiList,
  FiRefreshCw,
  FiServer,
  FiShield,
  FiShieldOff,
  FiSliders,
  FiTerminal,
  FiTrendingUp,
  FiUserCheck,
  FiUsers,
} from "react-icons/fi"
import type { AuditLogPublic, TacacsLogEvent } from "@/client"
import {
  AaaStatisticsService,
  AuditLogsService,
  HostsService,
  ProfilesService,
  RulesetsService,
  TacacsGroupsService,
  TacacsLogsService,
  TacacsUsersService,
} from "@/client"
import { AaaTrendChart } from "@/components/AaaStatistics/AaaTrendChart"
import { StatsExclusionsNote } from "@/components/AaaStatistics/StatsExclusions"
import { PageHeader } from "@/components/Common/PageHeader"
import useLogDays from "@/hooks/useLogDays"
import { formatDateTime, formatISODate, shiftISODate } from "@/utils"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
})

// ─── constants ────────────────────────────────────────────────────────────────

const LOG_TYPE_COLOR: Record<string, string> = {
  authentication: "blue",
  authorization: "purple",
  accounting: "teal",
}

const RESULT_COLOR: Record<string, string> = {
  success: "green",
  failed: "red",
  permit: "teal",
  deny: "orange",
  start: "blue",
  stop: "gray",
  unknown: "gray",
}

const ACTION_COLOR: Record<string, string> = {
  CREATE: "green",
  UPDATE: "blue",
  DELETE: "red",
  LOGIN_SUCCESS: "teal",
  LOGIN_FAILED: "orange",
}

// ─── types & filter helpers ───────────────────────────────────────────────────

type FilterMode = "7d" | "30d" | "custom"

const FILTER_LABELS: Record<FilterMode, string> = {
  "7d": "Last 7 Days",
  "30d": "Last 30 Days",
  custom: "Date Range",
}

const TREND_LABEL: Record<FilterMode, string> = {
  "7d": "Last 7 Days AAA Trend",
  "30d": "Last 30 Days AAA Trend",
  custom: "AAA Trend — Custom Range",
}

function getRangeDate(
  mode: FilterMode,
  customStart: string,
  customEnd: string,
  today: string,
): string | undefined {
  // `today` is the log time zone's day (useLogDays), not the browser's.
  if (mode === "7d") return `${shiftISODate(today, -6)},${today}`
  if (mode === "30d") return `${shiftISODate(today, -29)},${today}`
  if (customStart && customEnd) return `${customStart},${customEnd}`
  return undefined
}

// ─── helpers ──────────────────────────────────────────────────────────────────

interface RankedItem {
  name: string
  value: number
}

function buildRangeTrendData(stats: any) {
  if (!stats?.last_range_days_authentication_success) return []
  const toMap = (arr: any[]) =>
    Object.fromEntries(arr.map((d: any) => [d.date, d.count]))
  const authSuccess = toMap(stats.last_range_days_authentication_success)
  const authFail = toMap(stats.last_range_days_authentication_fail ?? [])
  const authzPermit = toMap(stats.last_range_days_authorization_permit ?? [])
  const authzDeny = toMap(stats.last_range_days_authorization_deny ?? [])
  const acctStart = toMap(stats.last_range_days_accounting_start ?? [])
  const acctStop = toMap(stats.last_range_days_accounting_stop ?? [])
  return (stats.last_range_days_authentication_success as any[]).map(
    (d: any) => ({
      date: formatISODate(d.date),
      "Auth Success": authSuccess[d.date] ?? 0,
      "Auth Fail": authFail[d.date] ?? 0,
      "Authz Permit": authzPermit[d.date] ?? 0,
      "Authz Deny": authzDeny[d.date] ?? 0,
      "Acct Start": acctStart[d.date] ?? 0,
      "Acct Stop": acctStop[d.date] ?? 0,
    }),
  )
}

// ─── sub-components ───────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string
  value: number | undefined
  subtitle: string
  icon: IconType
  colorPalette: "green" | "red" | "purple" | "blue" | "teal"
  badgeText?: string
}

function KpiCard({
  label,
  value,
  subtitle,
  icon: Icon,
  colorPalette,
  badgeText,
}: KpiCardProps) {
  const numValue = value ?? 0
  return (
    <Box
      p={4}
      bg="bg.panel"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="xl"
      shadow="xs"
      transition="all 0.18s ease"
      _hover={{ shadow: "sm", borderColor: `${colorPalette}.emphasized` }}
      h="100%"
    >
      <Flex align="center" justify="space-between" mb={2.5}>
        <HStack gap={2}>
          <Box
            w={2}
            h={2}
            borderRadius="full"
            bg={`${colorPalette}.500`}
            flexShrink={0}
          />
          <Text
            fontSize="xs"
            fontWeight="semibold"
            textTransform="uppercase"
            letterSpacing="wider"
            color="fg.muted"
          >
            {label}
          </Text>
        </HStack>
        <Box
          p={2}
          bg={`${colorPalette}.subtle`}
          color={`${colorPalette}.fg`}
          borderRadius="lg"
        >
          <Icon fontSize="16px" />
        </Box>
      </Flex>

      <Flex align="baseline" justify="space-between" gap={2}>
        <Text
          fontSize="3xl"
          fontWeight="bold"
          fontFamily="mono"
          lineHeight="1.1"
          letterSpacing="tight"
        >
          {numValue.toLocaleString()}
        </Text>
        {badgeText && (
          <Badge
            colorPalette={colorPalette}
            variant="subtle"
            size="sm"
            fontWeight="semibold"
          >
            {badgeText}
          </Badge>
        )}
      </Flex>

      <Text fontSize="xs" color="fg.subtle" mt={1.5}>
        {subtitle}
      </Text>
    </Box>
  )
}

interface TopRankedCardProps {
  title: string
  icon: IconType
  data: RankedItem[]
  colorPalette: "teal" | "green" | "purple" | "blue" | "red"
  mono?: boolean
}

function TopRankedCard({
  title,
  icon: Icon,
  data,
  colorPalette,
  mono = false,
}: TopRankedCardProps) {
  const total = data.reduce((sum, item) => sum + item.value, 0)
  const maxVal = data.reduce((max, item) => Math.max(max, item.value), 0)

  return (
    <Box
      p={4}
      bg="bg.panel"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="xl"
      shadow="xs"
      h="100%"
      display="flex"
      flexDirection="column"
    >
      <Flex align="center" justify="space-between" mb={3} gap={2}>
        <HStack gap={2} minW={0}>
          <Box
            p={1.5}
            bg={`${colorPalette}.subtle`}
            color={`${colorPalette}.fg`}
            borderRadius="md"
            flexShrink={0}
          >
            <Icon fontSize="14px" />
          </Box>
          <Heading size="xs" fontWeight="semibold" truncate>
            {title}
          </Heading>
        </HStack>
        {total > 0 && (
          <Badge
            size="sm"
            variant="subtle"
            colorPalette={colorPalette}
            fontFamily="mono"
            flexShrink={0}
          >
            {total.toLocaleString()}
          </Badge>
        )}
      </Flex>

      {data.length === 0 ? (
        <Flex
          direction="column"
          align="center"
          justify="center"
          flex="1"
          minH="132px"
          gap={1.5}
          bg="bg.subtle"
          borderRadius="lg"
          px={3}
        >
          <Box color="fg.subtle">
            <FiInbox fontSize="18px" />
          </Box>
          <Text color="fg.muted" fontSize="xs" fontWeight="medium">
            No activity
          </Text>
          <Text color="fg.subtle" fontSize="2xs" textAlign="center">
            No records in selected period
          </Text>
        </Flex>
      ) : (
        <Stack gap={2.5} flex="1" justify="flex-start">
          {data.slice(0, 5).map((item, idx) => {
            const pctOfMax = maxVal > 0 ? (item.value / maxVal) * 100 : 0
            const pctOfTotal =
              total > 0 ? Math.round((item.value / total) * 100) : 0
            return (
              <Box key={`${item.name}-${idx}`}>
                <Flex align="center" justify="space-between" gap={2} mb={1}>
                  <HStack gap={2} minW={0}>
                    <Text
                      fontSize="2xs"
                      fontFamily="mono"
                      color="fg.subtle"
                      w="14px"
                      flexShrink={0}
                    >
                      {idx + 1}.
                    </Text>
                    <Text
                      fontSize="xs"
                      fontWeight="medium"
                      fontFamily={mono ? "mono" : undefined}
                      truncate
                      title={item.name}
                    >
                      {item.name || "—"}
                    </Text>
                  </HStack>
                  <HStack gap={1.5} flexShrink={0}>
                    <Text fontSize="xs" fontWeight="semibold" fontFamily="mono">
                      {item.value.toLocaleString()}
                    </Text>
                    <Text
                      fontSize="2xs"
                      color="fg.subtle"
                      fontFamily="mono"
                      w="28px"
                      textAlign="right"
                    >
                      {pctOfTotal}%
                    </Text>
                  </HStack>
                </Flex>
                <Box
                  h="5px"
                  w="100%"
                  bg="bg.muted"
                  borderRadius="full"
                  overflow="hidden"
                >
                  <Box
                    h="100%"
                    w={`${Math.max(pctOfMax, 4)}%`}
                    bg={`${colorPalette}.500`}
                    borderRadius="full"
                    transition="width 0.3s ease"
                  />
                </Box>
              </Box>
            )
          })}
        </Stack>
      )}
    </Box>
  )
}

function FilterBar({
  mode,
  onMode,
  customStart,
  customEnd,
  onCustomStart,
  onCustomEnd,
}: {
  mode: FilterMode
  onMode: (m: FilterMode) => void
  customStart: string
  customEnd: string
  onCustomStart: (s: string) => void
  onCustomEnd: (s: string) => void
}) {
  return (
    <Flex gap={2.5} flexWrap="wrap" align="center">
      {/* Segmented mode selector — teal consistent with brand */}
      <Flex
        p={0.5}
        bg="bg.muted"
        borderRadius="lg"
        borderWidth="1px"
        borderColor="border.subtle"
        gap={0.5}
        flexShrink={0}
      >
        {(["7d", "30d", "custom"] as FilterMode[]).map((m) => {
          const active = mode === m
          return (
            <Button
              key={m}
              size="xs"
              variant={active ? "solid" : "ghost"}
              colorPalette={active ? "teal" : "gray"}
              borderRadius="md"
              px={3}
              fontWeight={active ? "semibold" : "medium"}
              onClick={() => onMode(m)}
            >
              {FILTER_LABELS[m]}
            </Button>
          )
        })}
      </Flex>

      {/* Date pickers — shown only in custom mode */}
      {mode === "custom" && (
        <Flex gap={2} align="center" flexShrink={0}>
          <Input
            size="xs"
            type="date"
            value={customStart}
            onChange={(e) => onCustomStart(e.target.value)}
            maxW="148px"
            minW="124px"
            bg="bg.panel"
          />
          <Text fontSize="xs" color="fg.muted" whiteSpace="nowrap">
            to
          </Text>
          <Input
            size="xs"
            type="date"
            value={customEnd}
            onChange={(e) => onCustomEnd(e.target.value)}
            maxW="148px"
            minW="124px"
            bg="bg.panel"
          />
        </Flex>
      )}
    </Flex>
  )
}

// ─── Today's AAA Summary (Bento Left) ─────────────────────────────────────────

function TodayLogSummary() {
  const { data, isLoading } = useQuery({
    queryKey: ["tacacs_log_summary_today"],
    queryFn: () => TacacsLogsService.getLogEventsSummary(),
    refetchInterval: 60_000,
  })

  const categories = [
    {
      label: "Authentication",
      primaryLabel: "Success",
      primaryValue: data?.authentication?.success ?? 0,
      primaryColor: "green",
      secondaryLabel: "Failed",
      secondaryValue: data?.authentication?.failed ?? 0,
      secondaryColor: "red",
    },
    {
      label: "Authorization",
      primaryLabel: "Permit",
      primaryValue: data?.authorization?.permit ?? 0,
      primaryColor: "teal",
      secondaryLabel: "Deny",
      secondaryValue: data?.authorization?.deny ?? 0,
      secondaryColor: "orange",
    },
    {
      label: "Accounting",
      primaryLabel: "Start",
      primaryValue: data?.accounting?.start ?? 0,
      primaryColor: "blue",
      secondaryLabel: "Stop",
      secondaryValue: data?.accounting?.stop ?? 0,
      secondaryColor: "gray",
    },
  ]

  return (
    <Box
      p={4}
      bg="bg.panel"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="xl"
      shadow="xs"
      h="100%"
      display="flex"
      flexDirection="column"
    >
      <Flex align="center" justify="space-between" mb={3.5}>
        <HStack gap={2}>
          <Box
            p={1.5}
            bg="teal.subtle"
            color="teal.fg"
            borderRadius="md"
            flexShrink={0}
          >
            <FiActivity fontSize="14px" />
          </Box>
          <Box>
            <Heading size="xs" fontWeight="semibold">
              Today&apos;s AAA Breakdown
            </Heading>
            <Text fontSize="2xs" color="fg.subtle">
              Live event distribution across AAA pipelines
            </Text>
          </Box>
        </HStack>
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        <Link to={"/tacacs_logs" as any}>
          <HStack
            gap={1}
            fontSize="xs"
            color="teal.fg"
            fontWeight="semibold"
            _hover={{ textDecoration: "underline" }}
          >
            <Text>View logs</Text>
            <FiArrowRight fontSize="12px" />
          </HStack>
        </Link>
      </Flex>

      <Grid
        templateColumns={{ base: "1fr", sm: "repeat(3, 1fr)" }}
        gap={3}
        flex="1"
      >
        {categories.map((cat) => {
          const total = cat.primaryValue + cat.secondaryValue
          const primaryPct = total > 0 ? (cat.primaryValue / total) * 100 : 0
          const secondaryPct =
            total > 0 ? (cat.secondaryValue / total) * 100 : 0

          return (
            <Flex
              key={cat.label}
              direction="column"
              justify="space-between"
              p={3.5}
              bg="bg.subtle"
              borderRadius="lg"
              borderWidth="1px"
              borderColor="border.subtle"
            >
              <Flex align="center" justify="space-between" mb={2.5}>
                <Text
                  fontSize="2xs"
                  fontWeight="bold"
                  textTransform="uppercase"
                  letterSpacing="wider"
                  color="fg.muted"
                >
                  {cat.label}
                </Text>
                <Text fontSize="xs" fontFamily="mono" color="fg.subtle">
                  {total.toLocaleString()}
                </Text>
              </Flex>

              {isLoading ? (
                <Skeleton height="40px" />
              ) : (
                <>
                  <Stack gap={1.5} mb={3}>
                    <Flex align="center" justify="space-between">
                      <HStack gap={1.5}>
                        <Box
                          w={2}
                          h={2}
                          borderRadius="full"
                          bg={`${cat.primaryColor}.500`}
                        />
                        <Text fontSize="xs" color="fg.muted">
                          {cat.primaryLabel}
                        </Text>
                      </HStack>
                      <Text fontSize="sm" fontWeight="bold" fontFamily="mono">
                        {cat.primaryValue.toLocaleString()}
                      </Text>
                    </Flex>
                    <Flex align="center" justify="space-between">
                      <HStack gap={1.5}>
                        <Box
                          w={2}
                          h={2}
                          borderRadius="full"
                          bg={`${cat.secondaryColor}.500`}
                        />
                        <Text fontSize="xs" color="fg.muted">
                          {cat.secondaryLabel}
                        </Text>
                      </HStack>
                      <Text fontSize="sm" fontWeight="bold" fontFamily="mono">
                        {cat.secondaryValue.toLocaleString()}
                      </Text>
                    </Flex>
                  </Stack>

                  {/* Proportional split bar */}
                  <Flex
                    h="5px"
                    w="100%"
                    bg="bg.muted"
                    borderRadius="full"
                    overflow="hidden"
                    gap="1px"
                  >
                    {total > 0 && (
                      <>
                        {primaryPct > 0 && (
                          <Box
                            h="100%"
                            w={`${primaryPct}%`}
                            bg={`${cat.primaryColor}.500`}
                          />
                        )}
                        {secondaryPct > 0 && (
                          <Box
                            h="100%"
                            w={`${secondaryPct}%`}
                            bg={`${cat.secondaryColor}.500`}
                          />
                        )}
                      </>
                    )}
                  </Flex>
                </>
              )}
            </Flex>
          )
        })}
      </Grid>
    </Box>
  )
}

// ─── Config Inventory (Bento Right) ───────────────────────────────────────────

interface ConfigItem {
  label: string
  to: string
  queryKey: string
  icon: IconType
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  fn: () => Promise<any>
}

const CONFIG_ITEMS: ConfigItem[] = [
  {
    label: "Hosts",
    to: "/hosts",
    queryKey: "config_count_hosts",
    icon: FiServer,
    fn: () => HostsService.readHosts({ limit: 1 }),
  },
  {
    label: "Users",
    to: "/tacacs_users",
    queryKey: "config_count_users",
    icon: FiUsers,
    fn: () => TacacsUsersService.readTacacsUsers({ limit: 1 }),
  },
  {
    label: "Groups",
    to: "/tacacs_groups",
    queryKey: "config_count_groups",
    icon: FiFolder,
    fn: () => TacacsGroupsService.readTacacsGroups({ limit: 1 }),
  },
  {
    label: "Profiles",
    to: "/profiles",
    queryKey: "config_count_profiles",
    icon: FiFileText,
    fn: () => ProfilesService.readProfiles({ limit: 1 }),
  },
  {
    label: "Rulesets",
    to: "/rulesets",
    queryKey: "config_count_rulesets",
    icon: FiSliders,
    fn: () => RulesetsService.readRulesets({ limit: 1 }),
  },
]

function ConfigInventoryTile({
  label,
  to,
  queryKey,
  fn,
  icon: Icon,
}: ConfigItem) {
  const { data, isLoading } = useQuery({ queryKey: [queryKey], queryFn: fn })
  return (
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    <Link to={to as any} style={{ display: "block", height: "100%" }}>
      <Flex
        align="center"
        justify="space-between"
        px={3}
        py={2.5}
        bg="bg.subtle"
        borderWidth="1px"
        borderColor="border.subtle"
        borderRadius="lg"
        h="100%"
        cursor="pointer"
        transition="all 0.15s ease"
        _hover={{
          borderColor: "teal.500",
          bg: "teal.subtle",
        }}
      >
        <HStack gap={2} minW={0}>
          <Box color="fg.muted" flexShrink={0}>
            <Icon fontSize="14px" />
          </Box>
          <Text fontSize="xs" fontWeight="medium" color="fg.muted" truncate>
            {label}
          </Text>
        </HStack>
        {isLoading ? (
          <Skeleton height="18px" width="24px" />
        ) : (
          <Text fontSize="md" fontWeight="bold" fontFamily="mono">
            {data?.count ?? 0}
          </Text>
        )}
      </Flex>
    </Link>
  )
}

function ConfigOverview() {
  return (
    <Box
      p={4}
      bg="bg.panel"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="xl"
      shadow="xs"
      h="100%"
      display="flex"
      flexDirection="column"
    >
      <Flex align="center" justify="space-between" mb={3.5}>
        <HStack gap={2}>
          <Box
            p={1.5}
            bg="teal.subtle"
            color="teal.fg"
            borderRadius="md"
            flexShrink={0}
          >
            <FiSliders fontSize="14px" />
          </Box>
          <Box>
            <Heading size="xs" fontWeight="semibold">
              TACACS+ Inventory
            </Heading>
            <Text fontSize="2xs" color="fg.subtle">
              Active configuration objects
            </Text>
          </Box>
        </HStack>
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        <Link to={"/tacacs_configs" as any}>
          <HStack
            gap={1}
            fontSize="xs"
            color="teal.fg"
            fontWeight="semibold"
            _hover={{ textDecoration: "underline" }}
          >
            <Text>Configs</Text>
            <FiArrowRight fontSize="12px" />
          </HStack>
        </Link>
      </Flex>

      <Grid
        templateColumns={{ base: "repeat(2, 1fr)", sm: "repeat(2, 1fr)" }}
        gap={2.5}
        flex="1"
      >
        {CONFIG_ITEMS.map((item, idx) => (
          <GridItem
            key={item.label}
            colSpan={idx === CONFIG_ITEMS.length - 1 ? 2 : 1}
          >
            <ConfigInventoryTile {...item} />
          </GridItem>
        ))}
      </Grid>
    </Box>
  )
}

// ─── Recent Audit Activity ────────────────────────────────────────────────────

function RecentActivity() {
  const { data, isLoading } = useQuery({
    queryKey: ["recent_audit_logs"],
    queryFn: () => AuditLogsService.readAuditLogs({ limit: 10 }),
  })

  const logs = data?.data ?? []

  return (
    <Box
      bg="bg.panel"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="xl"
      shadow="xs"
      overflow="hidden"
    >
      <Flex
        align="center"
        justify="space-between"
        px={4}
        py={3}
        borderBottomWidth="1px"
        borderColor="border.subtle"
      >
        <HStack gap={2}>
          <Box p={1.5} bg="teal.subtle" color="teal.fg" borderRadius="md">
            <FiList fontSize="14px" />
          </Box>
          <Heading size="xs" fontWeight="semibold">
            Recent User Activity
          </Heading>
          {!isLoading && (
            <Badge
              size="sm"
              variant="subtle"
              colorPalette="gray"
              fontFamily="mono"
            >
              {logs.length}
            </Badge>
          )}
        </HStack>
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        <Link to={"/audit_logs" as any}>
          <HStack
            gap={1}
            fontSize="xs"
            color="teal.fg"
            fontWeight="semibold"
            _hover={{ textDecoration: "underline" }}
          >
            <Text>View all</Text>
            <FiArrowRight fontSize="12px" />
          </HStack>
        </Link>
      </Flex>

      {isLoading ? (
        <Flex justify="center" py={8}>
          <Spinner size="sm" color="teal.500" />
        </Flex>
      ) : logs.length === 0 ? (
        <Flex align="center" justify="center" gap={2} py={6} color="fg.muted">
          <FiInbox fontSize="16px" />
          <Text fontSize="xs">No recent user activity recorded.</Text>
        </Flex>
      ) : (
        <Box overflowX="auto">
          <Table.Root size="sm" variant="line">
            <Table.Header bg="bg.subtle">
              <Table.Row>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  Time
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  User
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  Action
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  Entity
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  Description
                </Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {logs.map((log: AuditLogPublic) => (
                <Table.Row key={log.id} _hover={{ bg: "bg.subtle" }}>
                  <Table.Cell
                    whiteSpace="nowrap"
                    fontSize="xs"
                    color="fg.muted"
                    fontFamily="mono"
                  >
                    {formatDateTime(log.created_at, {
                      hour12: false,
                    })}
                  </Table.Cell>
                  <Table.Cell
                    fontSize="xs"
                    maxW="40"
                    truncate
                    fontWeight="medium"
                    title={log.user_email ?? undefined}
                  >
                    {log.user_email}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      colorPalette={ACTION_COLOR[log.action] ?? "gray"}
                      size="sm"
                      variant="subtle"
                    >
                      {log.action}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell
                    fontSize="xs"
                    fontFamily="mono"
                    whiteSpace="nowrap"
                  >
                    {log.entity_type}
                    {log.entity_id ? ` #${log.entity_id.slice(0, 8)}` : ""}
                  </Table.Cell>
                  <Table.Cell
                    fontSize="xs"
                    maxW="64"
                    truncate
                    color="fg.muted"
                    title={log.description ?? undefined}
                  >
                    {log.description ?? "—"}
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Box>
      )}
    </Box>
  )
}

// ─── Last TACACS Logs ─────────────────────────────────────────────────────────

function LastTacacsLogs() {
  const { today, daysAgo } = useLogDays()
  const sevenDaysAgo = daysAgo(7)
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard_last_tacacs_logs", today],
    queryFn: () =>
      TacacsLogsService.listLogEvents({
        date_from: sevenDaysAgo,
        date_to: today,
        limit: 20,
      }),
  })

  const logs = data?.data ?? []

  return (
    <Box
      bg="bg.panel"
      borderWidth="1px"
      borderColor="border.subtle"
      borderRadius="xl"
      shadow="xs"
      overflow="hidden"
    >
      <Flex
        align="center"
        justify="space-between"
        px={4}
        py={3}
        borderBottomWidth="1px"
        borderColor="border.subtle"
      >
        <HStack gap={2}>
          <Box p={1.5} bg="teal.subtle" color="teal.fg" borderRadius="md">
            <FiTerminal fontSize="14px" />
          </Box>
          <Heading size="xs" fontWeight="semibold">
            Last TACACS Logs
          </Heading>
          {!isLoading && (
            <Badge
              size="sm"
              variant="subtle"
              colorPalette="gray"
              fontFamily="mono"
            >
              {logs.length}
            </Badge>
          )}
          <Text
            fontSize="2xs"
            color="fg.subtle"
            display={{ base: "none", sm: "inline" }}
          >
            Last 7 days
          </Text>
        </HStack>
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        <Link to={"/tacacs_logs" as any}>
          <HStack
            gap={1}
            fontSize="xs"
            color="teal.fg"
            fontWeight="semibold"
            _hover={{ textDecoration: "underline" }}
          >
            <Text>View all</Text>
            <FiArrowRight fontSize="12px" />
          </HStack>
        </Link>
      </Flex>

      {isLoading ? (
        <Flex justify="center" py={8}>
          <Spinner size="sm" color="teal.500" />
        </Flex>
      ) : logs.length === 0 ? (
        <Flex align="center" justify="center" gap={2} py={6} color="fg.muted">
          <FiInbox fontSize="16px" />
          <Text fontSize="xs">No TACACS logs recorded in the last 7 days.</Text>
        </Flex>
      ) : (
        <Box overflowX="auto">
          <Table.Root size="sm" variant="line">
            <Table.Header bg="bg.subtle">
              <Table.Row>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  Time
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  Type
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  User
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  NAS IP
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  Client IP
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  Result
                </Table.ColumnHeader>
                <Table.ColumnHeader
                  fontSize="2xs"
                  textTransform="uppercase"
                  color="fg.muted"
                >
                  Command
                </Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {logs.map((log: TacacsLogEvent, i: number) => (
                <Table.Row key={i} _hover={{ bg: "bg.subtle" }}>
                  <Table.Cell
                    whiteSpace="nowrap"
                    fontSize="xs"
                    color="fg.muted"
                    fontFamily="mono"
                  >
                    {formatDateTime(
                      log.timestamp.replace(
                        /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) ([+-]\d{2})(\d{2})$/,
                        "$1T$2$3:$4",
                      ),
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      colorPalette={LOG_TYPE_COLOR[log.log_type] ?? "gray"}
                      size="sm"
                      variant="subtle"
                    >
                      {log.log_type}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell
                    fontSize="xs"
                    maxW="28"
                    truncate
                    fontWeight="medium"
                  >
                    {log.username ?? "—"}
                  </Table.Cell>
                  <Table.Cell fontSize="xs" color="fg.muted" fontFamily="mono">
                    {log.nas_ip}
                  </Table.Cell>
                  <Table.Cell fontSize="xs" color="fg.muted" fontFamily="mono">
                    {log.client_ip ?? "—"}
                  </Table.Cell>
                  <Table.Cell>
                    <Badge
                      colorPalette={
                        RESULT_COLOR[log.result?.toLowerCase()] ?? "gray"
                      }
                      size="sm"
                      variant="subtle"
                    >
                      {log.result?.toUpperCase()}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell
                    fontSize="xs"
                    maxW="48"
                    truncate
                    color="fg.muted"
                    title={log.command || undefined}
                    fontFamily="mono"
                  >
                    {log.command ?? "—"}
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>
        </Box>
      )}
    </Box>
  )
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

function Dashboard() {
  const [filterMode, setFilterMode] = useState<FilterMode>("7d")
  const [customStart, setCustomStart] = useState("")
  const [customEnd, setCustomEnd] = useState("")
  const queryClient = useQueryClient()

  const { today: logToday } = useLogDays()
  const rangeDate = getRangeDate(filterMode, customStart, customEnd, logToday)

  const {
    data: stats,
    isLoading,
    error,
    isFetching,
    dataUpdatedAt,
  } = useQuery({
    queryKey: ["aaa_statistics"],
    queryFn: () => AaaStatisticsService.readAaaStatistics(),
    refetchInterval: 60_000,
  })

  const { data: rangeStats, isLoading: rangeLoading } = useQuery({
    queryKey: ["aaa_statistics_range", rangeDate],
    queryFn: () =>
      AaaStatisticsService.readAaaStatisticsRange({ range_date: rangeDate }),
    enabled: !!rangeDate,
    refetchInterval: 300_000,
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["aaa_statistics"] })
    queryClient.invalidateQueries({ queryKey: ["tacacs_log_summary_today"] })
    queryClient.invalidateQueries({ queryKey: ["recent_audit_logs"] })
    queryClient.invalidateQueries({ queryKey: ["dashboard_last_tacacs_logs"] })
    queryClient.invalidateQueries({ queryKey: ["aaa_statistics_range"] })
  }

  const chartsLoading = rangeLoading

  const todaySuccess = stats?.today_successful_logins ?? 0
  const todayFailed = stats?.today_failed_logins ?? 0
  const todayTotalAuth = todaySuccess + todayFailed
  const passRate =
    todayTotalAuth > 0
      ? `${Math.round((todaySuccess / todayTotalAuth) * 100)}% pass`
      : undefined
  const failRate =
    todayTotalAuth > 0 && todayFailed > 0
      ? `${Math.round((todayFailed / todayTotalAuth) * 100)}% fail`
      : undefined

  const topSuccessByUser: RankedItem[] = (
    rangeStats?.authentication_success_count_by_user ?? []
  ).map((u: any) => ({
    name: String(u.username ?? ""),
    value: Number(u.success_count ?? 0),
  }))

  const topSuccessByIp: RankedItem[] = (
    rangeStats?.authentication_success_count_by_user_source_ip ?? []
  ).map((u: any) => ({
    name: String(u.user_source_ip ?? ""),
    value: Number(u.success_count ?? 0),
  }))

  const topSuccessByNas: RankedItem[] = (
    rangeStats?.authentication_success_count_by_nas_ip ?? []
  ).map((u: any) => ({
    name: String(u.nas_ip ?? ""),
    value: Number(u.success_count ?? 0),
  }))

  const topFailedByUser: RankedItem[] = (
    rangeStats?.authentication_failed_count_by_user ?? []
  ).map((u: any) => ({
    name: String(u.username ?? ""),
    value: Number(u.fail_count ?? 0),
  }))

  const trendData = buildRangeTrendData(rangeStats)
  const trendEmpty = trendData.length === 0

  const rangeSubtitle =
    filterMode === "custom" && customStart && customEnd
      ? `${customStart} → ${customEnd}`
      : filterMode === "custom"
        ? "Select start and end date"
        : FILTER_LABELS[filterMode]

  return (
    <Container maxW="full" py={6}>
      {/* Header Bar */}
      <Flex
        justify="space-between"
        align={{ base: "flex-start", md: "flex-end" }}
        mb={5}
        gap={3}
        wrap="wrap"
      >
        <PageHeader
          title="Security & Analytics Dashboard"
          description="Real-time TACACS+ server metrics, access trends, configuration overview, and audit logs."
          icon={FiTrendingUp}
        />
        <Flex align="center" gap={2.5} wrap="wrap">
          <StatsExclusionsNote />
          {dataUpdatedAt > 0 && (
            <Flex
              color="fg.muted"
              fontSize="xs"
              align="center"
              gap={1.5}
              px={2.5}
              py={1}
              bg="bg.subtle"
              borderWidth="1px"
              borderColor="border.subtle"
              borderRadius="md"
              fontFamily="mono"
            >
              <FiClock fontSize="12px" />
              <Text>
                {new Date(dataUpdatedAt).toLocaleTimeString("en-US", {
                  hour12: false,
                })}
              </Text>
            </Flex>
          )}
          <IconButton
            variant="outline"
            size="sm"
            aria-label="Refresh dashboard"
            onClick={handleRefresh}
            loading={isFetching}
            colorPalette="teal"
          >
            <FiRefreshCw />
          </IconButton>
        </Flex>
      </Flex>

      {isLoading ? (
        <Flex justify="center" align="center" height="50vh">
          <Spinner size="xl" color="teal.500" />
        </Flex>
      ) : error ? (
        <Box
          p={4}
          borderWidth="1px"
          borderRadius="xl"
          borderColor="red.300"
          bg="red.subtle"
        >
          <Text color="red.fg" fontSize="sm">
            Error fetching statistics: {error.message}
          </Text>
        </Box>
      ) : (
        <Stack gap={5}>
          {/* Band 1: Today's KPI Bento Row */}
          <Grid
            templateColumns={{
              base: "1fr",
              sm: "repeat(2, 1fr)",
              lg: "repeat(4, 1fr)",
            }}
            gap={4}
          >
            <KpiCard
              label="Auth Success"
              value={stats?.today_successful_logins}
              subtitle="Successful logins today"
              icon={FiShield}
              colorPalette="green"
              badgeText={passRate}
            />
            <KpiCard
              label="Auth Failed"
              value={stats?.today_failed_logins}
              subtitle="Failed login attempts today"
              icon={FiShieldOff}
              colorPalette="red"
              badgeText={failRate}
            />
            <KpiCard
              label="Unique Source IPs"
              value={stats?.today_unique_user_source_ip_count}
              subtitle="Distinct client sources today"
              icon={FiGlobe}
              colorPalette="purple"
            />
            <KpiCard
              label="Unique NAS IPs"
              value={stats?.today_unique_nas_ip_count}
              subtitle="Active network devices today"
              icon={FiServer}
              colorPalette="blue"
            />
          </Grid>

          {/* Band 2: Bento Split — Today's AAA Breakdown + TACACS Inventory */}
          <Grid
            templateColumns={{ base: "1fr", lg: "repeat(12, 1fr)" }}
            gap={4}
            alignItems="stretch"
          >
            <GridItem colSpan={{ base: 1, lg: 8 }}>
              <TodayLogSummary />
            </GridItem>
            <GridItem colSpan={{ base: 1, lg: 4 }}>
              <ConfigOverview />
            </GridItem>
          </Grid>

          {/* Band 3: Analytics — Unified Filter + Hero Trend Chart + Top 5 Ranked Lists */}
          <Stack gap={4}>
            <Flex
              align="center"
              justify="space-between"
              flexWrap="wrap"
              gap={3}
              px={4}
              py={3}
              bg="bg.panel"
              borderWidth="1px"
              borderColor="border.subtle"
              borderRadius="xl"
              shadow="xs"
            >
              <HStack gap={2.5}>
                <Box p={1.5} bg="teal.subtle" color="teal.fg" borderRadius="md">
                  <FiTrendingUp fontSize="14px" />
                </Box>
                <Box>
                  <Heading size="xs" fontWeight="semibold">
                    AAA Trends &amp; Top Contributors
                  </Heading>
                  <Text fontSize="2xs" color="fg.muted">
                    {rangeSubtitle}
                  </Text>
                </Box>
              </HStack>
              <FilterBar
                mode={filterMode}
                onMode={setFilterMode}
                customStart={customStart}
                customEnd={customEnd}
                onCustomStart={setCustomStart}
                onCustomEnd={setCustomEnd}
              />
            </Flex>

            {/* Hero AAA Trend Chart */}
            <Box
              p={4}
              bg="bg.panel"
              borderWidth="1px"
              borderColor="border.subtle"
              borderRadius="xl"
              shadow="xs"
            >
              <Flex
                align="center"
                justify="space-between"
                mb={3}
                wrap="wrap"
                gap={2}
              >
                <Heading size="xs" fontWeight="semibold">
                  {TREND_LABEL[filterMode]}
                </Heading>
                <Text fontSize="2xs" color="fg.subtle">
                  Click legend to isolate · Shift-click to toggle
                </Text>
              </Flex>
              {chartsLoading ? (
                <Flex justify="center" py={10}>
                  <Spinner size="md" color="teal.500" />
                </Flex>
              ) : trendEmpty ? (
                <Flex
                  direction="column"
                  align="center"
                  justify="center"
                  h="200px"
                  gap={2}
                  bg="bg.subtle"
                  borderRadius="lg"
                >
                  <Box color="fg.subtle">
                    <FiTrendingUp fontSize="22px" />
                  </Box>
                  <Text color="fg.muted" fontSize="xs" fontWeight="semibold">
                    No trend data
                  </Text>
                  <Text color="fg.subtle" fontSize="2xs">
                    Statistics aggregate periodically — try a wider range
                  </Text>
                </Flex>
              ) : (
                <AaaTrendChart
                  data={trendData}
                  height={265}
                  margin={{ top: 8, right: 16, left: -8, bottom: 0 }}
                />
              )}
            </Box>

            {/* Top 5 Ranked Horizontal Bar Lists */}
            {chartsLoading ? (
              <Grid
                templateColumns={{
                  base: "1fr",
                  md: "repeat(2, 1fr)",
                  xl: "repeat(4, 1fr)",
                }}
                gap={4}
              >
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} height="190px" borderRadius="xl" />
                ))}
              </Grid>
            ) : (
              <Grid
                templateColumns={{
                  base: "1fr",
                  md: "repeat(2, 1fr)",
                  xl: "repeat(4, 1fr)",
                }}
                gap={4}
              >
                <TopRankedCard
                  title="Top 5 Users — Success"
                  icon={FiUserCheck}
                  data={topSuccessByUser}
                  colorPalette="green"
                />
                <TopRankedCard
                  title="Top 5 Source IPs"
                  icon={FiGlobe}
                  data={topSuccessByIp}
                  colorPalette="purple"
                  mono
                />
                <TopRankedCard
                  title="Top 5 NAS IPs"
                  icon={FiServer}
                  data={topSuccessByNas}
                  colorPalette="blue"
                  mono
                />
                <TopRankedCard
                  title="Top 5 Users — Failed"
                  icon={FiShieldOff}
                  data={topFailedByUser}
                  colorPalette="red"
                />
              </Grid>
            )}
          </Stack>

          {/* Band 4: Operational Logs & Audit Tables */}
          <LastTacacsLogs />
          <RecentActivity />
        </Stack>
      )}
    </Container>
  )
}
