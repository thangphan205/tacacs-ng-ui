import { Badge, Text } from "@chakra-ui/react"

const MS_PER_DAY = 24 * 60 * 60 * 1000

/** Whole days from today until `date` (YYYY-MM-DD, last valid day). Negative once expired. */
export function daysRemaining(date: string, now: Date = new Date()): number {
  const [year, month, day] = date.split("-").map(Number)
  const end = Date.UTC(year, month - 1, day)
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((end - today) / MS_PER_DAY)
}

interface ExpiryBadgeProps {
  date?: string | null
}

export const ExpiryBadge = ({ date }: ExpiryBadgeProps) => {
  if (!date) {
    return <Text color="gray">Never</Text>
  }
  const days = daysRemaining(date)
  if (days < 0) {
    return (
      <Badge colorPalette="red" title={date}>
        Expired
      </Badge>
    )
  }
  const label = days === 0 ? "Today" : `${days} day${days === 1 ? "" : "s"}`
  return (
    <Badge colorPalette={days <= 7 ? "orange" : "green"} title={date}>
      {label}
    </Badge>
  )
}

export default ExpiryBadge
