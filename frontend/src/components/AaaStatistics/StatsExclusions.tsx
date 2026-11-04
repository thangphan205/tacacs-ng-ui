import {
  Badge,
  Box,
  Button,
  DialogTitle,
  Flex,
  IconButton,
  Input,
  Text,
  VStack,
} from "@chakra-ui/react"
import {
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { FiEyeOff, FiPlus, FiSettings, FiTrash2 } from "react-icons/fi"

import type { ApiError } from "@/api"
import { type StatsExcludedUserCreate, StatsExclusionsService } from "@/client"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Field } from "@/components/ui/field"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const STATS_EXCLUSIONS_QUERY_KEY = ["stats_exclusions"]

// Every query whose numbers depend on the exclusion list.
const STATS_QUERY_KEYS = [
  STATS_EXCLUSIONS_QUERY_KEY,
  ["aaa_statistics"],
  ["aaa_statistics_range"],
  ["aaa_node_stats"],
  ["tacacs_log_summary_today"],
]

function invalidateStats(queryClient: QueryClient): void {
  for (const queryKey of STATS_QUERY_KEYS) {
    queryClient.invalidateQueries({ queryKey })
  }
}

export function useStatsExclusions() {
  return useQuery({
    queryKey: STATS_EXCLUSIONS_QUERY_KEY,
    queryFn: () => StatsExclusionsService.readStatsExclusions(),
  })
}

/** Short "N accounts excluded" note for widgets outside the statistics page. */
export function StatsExclusionsNote() {
  const { data } = useStatsExclusions()
  const count = data?.count ?? 0
  if (count === 0) return null
  return (
    <Flex align="center" gap={1.5} color="fg.muted" fontSize="xs">
      <FiEyeOff />
      <Text title={data?.data.map((row) => row.pattern).join(", ")}>
        {count} {count === 1 ? "account" : "accounts"} excluded from statistics
      </Text>
    </Flex>
  )
}

function ManageStatsExclusions() {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const { data } = useStatsExclusions()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<StatsExcludedUserCreate>({
    defaultValues: { pattern: "", note: "" },
  })

  const createMutation = useMutation({
    mutationFn: (body: StatsExcludedUserCreate) =>
      StatsExclusionsService.createStatsExclusion({
        statsExcludedUserCreate: {
          pattern: body.pattern,
          note: body.note || null,
        },
      }),
    onSuccess: (row) => {
      showSuccessToast(`'${row.pattern}' is now excluded from statistics.`)
      reset()
    },
    onError: (err: ApiError) => handleError(err),
    onSettled: () => invalidateStats(queryClient),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      StatsExclusionsService.deleteStatsExclusion({ id }),
    onSuccess: () => showSuccessToast("Exclusion removed."),
    onError: (err: ApiError) => handleError(err),
    onSettled: () => invalidateStats(queryClient),
  })

  const rows = data?.data ?? []

  return (
    <DialogRoot
      size={{ base: "xs", md: "md" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost" size="xs">
          <FiSettings fontSize="14px" />
          Manage
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogCloseTrigger />
        <DialogHeader>
          <DialogTitle>Accounts excluded from statistics</DialogTitle>
        </DialogHeader>
        <DialogBody>
          <VStack align="stretch" gap={4}>
            <Text fontSize="sm" color="fg.muted">
              Service and automation accounts listed here are left out of the
              AAA statistics and dashboards, including past days. They still
              authenticate normally, and their events still reach the raw logs,
              the log viewer, alerting and SIEM forwarding.
            </Text>

            <form
              noValidate
              onSubmit={handleSubmit((body) => createMutation.mutate(body))}
            >
              <VStack align="stretch" gap={2}>
                <Field
                  label="Username or pattern"
                  invalid={!!errors.pattern}
                  errorText={errors.pattern?.message}
                  helperText="Exact username, or use * as a wildcard (e.g. svc_*). Case-insensitive."
                >
                  <Input
                    {...register("pattern", {
                      required: "Pattern is required.",
                      pattern: {
                        value: /^[\w.*-]+$/,
                        message:
                          "Use letters, digits, '_', '.', '-' and '*' only.",
                      },
                      validate: (v) =>
                        v.replace(/\*/g, "").trim() !== "" ||
                        "A pattern of only '*' would exclude every user.",
                    })}
                    placeholder="data_collector"
                  />
                </Field>
                <Field label="Note" optionalText=" (optional)">
                  <Input
                    {...register("note")}
                    placeholder="Inventory collector, every 30 min"
                  />
                </Field>
                <Button
                  type="submit"
                  size="sm"
                  alignSelf="flex-start"
                  loading={isSubmitting || createMutation.isPending}
                >
                  <FiPlus />
                  Add exclusion
                </Button>
              </VStack>
            </form>

            <VStack align="stretch" gap={1}>
              {rows.length === 0 ? (
                <Text fontSize="sm" color="fg.subtle">
                  No accounts are excluded.
                </Text>
              ) : (
                rows.map((row) => (
                  <Flex
                    key={row.id}
                    align="center"
                    justify="space-between"
                    gap={2}
                    px={2}
                    py={1}
                    borderWidth="1px"
                    borderRadius="md"
                  >
                    <Box minW={0}>
                      <Text fontFamily="mono" fontSize="sm" truncate>
                        {row.pattern}
                      </Text>
                      {row.note && (
                        <Text fontSize="xs" color="fg.muted" truncate>
                          {row.note}
                        </Text>
                      )}
                    </Box>
                    <IconButton
                      aria-label={`Remove ${row.pattern}`}
                      variant="ghost"
                      size="xs"
                      colorPalette="red"
                      loading={
                        deleteMutation.isPending &&
                        deleteMutation.variables === row.id
                      }
                      onClick={() => deleteMutation.mutate(row.id)}
                    >
                      <FiTrash2 />
                    </IconButton>
                  </Flex>
                ))
              )}
            </VStack>
          </VStack>
        </DialogBody>
        <DialogFooter />
      </DialogContent>
    </DialogRoot>
  )
}

interface StatsExclusionsBarProps {
  includeExcluded: boolean
  onIncludeExcludedChange: (value: boolean) => void
}

/**
 * Says when statistics are filtered, so nobody reads filtered numbers as totals,
 * and lets the viewer temporarily include the excluded accounts.
 */
export function StatsExclusionsBar({
  includeExcluded,
  onIncludeExcludedChange,
}: StatsExclusionsBarProps) {
  const { user } = useAuth()
  const { data } = useStatsExclusions()
  const rows = data?.data ?? []
  const isSuperuser = !!user?.is_superuser

  if (rows.length === 0 && !isSuperuser) return null

  return (
    <Flex
      mt={4}
      px={4}
      py={2}
      gap={3}
      align="center"
      justify="space-between"
      wrap="wrap"
      borderWidth="1px"
      borderRadius="lg"
      bg={rows.length > 0 && !includeExcluded ? "bg.info" : "bg.panel"}
    >
      <Flex align="center" gap={2} wrap="wrap" minW={0}>
        <FiEyeOff />
        {rows.length === 0 ? (
          <Text fontSize="sm" color="fg.muted">
            No accounts are excluded from statistics.
          </Text>
        ) : (
          <>
            <Text fontSize="sm" fontWeight="medium">
              {includeExcluded
                ? `Showing all accounts, including ${rows.length} normally excluded:`
                : `${rows.length} ${rows.length === 1 ? "account" : "accounts"} excluded from these statistics:`}
            </Text>
            {rows.map((row) => (
              <Badge
                key={row.id}
                variant="outline"
                fontFamily="mono"
                title={row.note ?? undefined}
              >
                {row.pattern}
              </Badge>
            ))}
          </>
        )}
      </Flex>
      <Flex align="center" gap={3}>
        {rows.length > 0 && (
          <Checkbox
            size="sm"
            checked={includeExcluded}
            onCheckedChange={({ checked }) =>
              onIncludeExcludedChange(checked === true)
            }
          >
            Include excluded
          </Checkbox>
        )}
        {isSuperuser && <ManageStatsExclusions />}
      </Flex>
    </Flex>
  )
}
