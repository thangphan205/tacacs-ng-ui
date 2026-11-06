import {
  createListCollection,
  Flex,
  IconButton,
  Select,
  Text,
} from "@chakra-ui/react"
import { FiClock, FiRefreshCw } from "react-icons/fi"

/** Auto-refresh choices in milliseconds; 0 means off. */
export const AUTO_REFRESH_OPTIONS = [0, 10_000, 30_000, 60_000] as const

const intervalCollection = createListCollection({
  items: AUTO_REFRESH_OPTIONS.map((ms) => ({
    value: String(ms),
    label: ms === 0 ? "Auto: off" : `Auto: ${ms / 1000}s`,
  })),
})

interface RefreshControlProps {
  /** Refetch the view's queries without touching its filters or page. */
  onRefresh: () => void
  isFetching: boolean
  /** `dataUpdatedAt` of the main query; 0 hides the "Updated" time. */
  dataUpdatedAt: number
  ariaLabel?: string
  /** Pass both to show the auto-refresh select. */
  autoRefreshMs?: number
  onAutoRefreshChange?: (ms: number) => void
  /** Shown as the select's tooltip when auto-refresh is set but held. */
  autoRefreshPausedReason?: string
}

export function RefreshControl({
  onRefresh,
  isFetching,
  dataUpdatedAt,
  ariaLabel = "Refresh",
  autoRefreshMs,
  onAutoRefreshChange,
  autoRefreshPausedReason,
}: RefreshControlProps) {
  const paused = !!autoRefreshMs && !!autoRefreshPausedReason

  return (
    <Flex align="center" gap={2} flexShrink={0}>
      {dataUpdatedAt > 0 && (
        <Flex color="fg.muted" fontSize="xs" align="center" gap={1}>
          <FiClock />
          <Text whiteSpace="nowrap">
            Updated{" "}
            {new Date(dataUpdatedAt).toLocaleTimeString("en-US", {
              hour12: false,
            })}
            {paused && " · paused"}
          </Text>
        </Flex>
      )}
      {autoRefreshMs !== undefined && onAutoRefreshChange && (
        <Select.Root
          collection={intervalCollection}
          value={[String(autoRefreshMs)]}
          onValueChange={({ value }) => onAutoRefreshChange(Number(value[0]))}
          size="sm"
          width="auto"
          title={paused ? autoRefreshPausedReason : undefined}
        >
          <Select.Control>
            <Select.Trigger minW="110px" whiteSpace="nowrap">
              <Select.ValueText />
            </Select.Trigger>
            <Select.IndicatorGroup>
              <Select.Indicator />
            </Select.IndicatorGroup>
          </Select.Control>
          <Select.Positioner>
            <Select.Content minW="120px">
              <Select.ItemGroup>
                {intervalCollection.items.map((item) => (
                  <Select.Item
                    key={item.value}
                    item={item.value}
                    whiteSpace="nowrap"
                  >
                    {item.label}
                    <Select.ItemIndicator />
                  </Select.Item>
                ))}
              </Select.ItemGroup>
            </Select.Content>
          </Select.Positioner>
        </Select.Root>
      )}
      <IconButton
        variant="outline"
        size="sm"
        aria-label={ariaLabel}
        title={ariaLabel}
        onClick={onRefresh}
        loading={isFetching}
        colorPalette="teal"
      >
        <FiRefreshCw />
      </IconButton>
    </Flex>
  )
}
