import { useQuery } from "@tanstack/react-query"

import { TacacsNgSettingsService } from "@/client"
import { shiftISODate, toLocalISODate } from "@/utils"

/**
 * Days in the log time zone (TacacsNgSetting.timezone): the zone tac_plus-ng
 * names its log files in and the statistics are kept by. Until the setting
 * loads, or if it is empty, the browser's zone is used.
 */
const useLogDays = () => {
  const { data } = useQuery({
    queryKey: ["tacacs_ng_settings"],
    queryFn: () => TacacsNgSettingsService.readTacacsNgSettings(),
    staleTime: 5 * 60 * 1000,
  })
  const timeZone = data?.timezone || undefined
  const today = toLocalISODate(new Date(), timeZone)
  return {
    timeZone,
    today,
    yesterday: shiftISODate(today, -1),
    daysAgo: (n: number) => shiftISODate(today, -n),
  }
}

export default useLogDays
