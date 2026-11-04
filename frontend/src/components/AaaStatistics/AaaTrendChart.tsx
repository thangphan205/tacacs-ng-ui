import { Box, Button, Flex } from "@chakra-ui/react"
import { useState } from "react"
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export interface TrendSeries {
  key: string
  /** Chakra colour palette name, rendered as `--chakra-colors-<color>-500`. */
  color: string
}

export const AAA_TREND_SERIES: TrendSeries[] = [
  { key: "Auth Success", color: "green" },
  { key: "Auth Fail", color: "red" },
  { key: "Authz Permit", color: "blue" },
  { key: "Authz Deny", color: "orange" },
  { key: "Acct Start", color: "purple" },
  { key: "Acct Stop", color: "gray" },
]

/**
 * Which series are shown after a legend click. `null` means all of them.
 *
 * - Plain click: show only `key`; clicking the sole visible series shows all.
 * - Additive (Shift/Ctrl/Cmd) click: add or remove `key`.
 * - A selection that ends up empty or complete collapses back to `null`.
 */
export function nextVisible(
  visible: string[] | null,
  key: string,
  additive: boolean,
  allKeys: string[],
): string[] | null {
  if (!additive) {
    return visible?.length === 1 && visible[0] === key ? null : [key]
  }
  const current = visible ?? allKeys
  const next = current.includes(key)
    ? current.filter((k) => k !== key)
    : allKeys.filter((k) => k === key || current.includes(k))
  return next.length === 0 || next.length === allKeys.length ? null : next
}

interface AaaTrendChartProps {
  data: Record<string, unknown>[]
  series?: TrendSeries[]
  height: number
  margin?: { top?: number; right?: number; bottom?: number; left?: number }
  /** Smaller ticks, legend and strokes, for the Node Comparison cards. */
  compact?: boolean
}

/**
 * AAA trend line chart whose legend filters the lines: click a series to see
 * it alone (the Y-axis rescales, since recharts leaves hidden lines out of the
 * domain), Shift/Ctrl/Cmd-click to add or remove one.
 */
export function AaaTrendChart({
  data,
  series = AAA_TREND_SERIES,
  height,
  margin = { top: 10, right: 30, left: -20, bottom: 0 },
  compact = false,
}: AaaTrendChartProps) {
  const [visible, setVisible] = useState<string[] | null>(null)
  const keys = series.map((s) => s.key)
  const isShown = (key: string) => visible === null || visible.includes(key)
  const tickStyle = {
    fontSize: compact ? 9 : 11,
    fill: "var(--chakra-colors-fg-muted)",
  }

  const legend = (
    <Flex
      justify="center"
      align="center"
      wrap="wrap"
      gap={compact ? 0 : 1}
      pt={compact ? 1 : 2}
    >
      {series.map(({ key, color }) => {
        const shown = isShown(key)
        return (
          <Button
            key={key}
            variant="ghost"
            size="xs"
            h={compact ? 5 : 6}
            px={compact ? 1 : 2}
            fontSize={compact ? "2xs" : "xs"}
            fontWeight="medium"
            color={shown ? `${color}.fg` : "fg.subtle"}
            opacity={shown ? 1 : 0.55}
            aria-pressed={shown}
            title="Click to show only this · Shift-click to add or remove"
            onClick={(e) =>
              setVisible((v) =>
                nextVisible(v, key, e.shiftKey || e.ctrlKey || e.metaKey, keys),
              )
            }
          >
            <Box
              as="span"
              w={2}
              h={2}
              borderRadius="full"
              bg={shown ? `${color}.500` : "fg.subtle"}
            />
            {key}
          </Button>
        )
      })}
      {visible !== null && (
        <Button
          variant="plain"
          size="xs"
          h={compact ? 5 : 6}
          px={compact ? 1 : 2}
          fontSize={compact ? "2xs" : "xs"}
          color="fg.muted"
          textDecoration="underline"
          onClick={() => setVisible(null)}
        >
          Show all
        </Button>
      )}
    </Flex>
  )

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={margin}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="var(--chakra-colors-border)"
        />
        <XAxis dataKey="date" tick={tickStyle} />
        <YAxis tick={tickStyle} allowDecimals={false} />
        <Tooltip />
        <Legend content={() => legend} />
        {series.map(({ key, color }) => (
          <Line
            key={key}
            dataKey={key}
            type="monotone"
            hide={!isShown(key)}
            stroke={`var(--chakra-colors-${color}-500)`}
            strokeWidth={compact ? 1.5 : 2}
            dot={false}
            activeDot={{ r: compact ? 3 : 4 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
