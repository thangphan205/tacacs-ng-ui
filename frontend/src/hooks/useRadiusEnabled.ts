import { useQuery } from "@tanstack/react-query"

import { TacacsNgSettingsService } from "@/client"

/**
 * Whether RADIUS is enabled (TacacsNgSetting.radius_enabled). RADIUS is off by
 * default; while it is, RADIUS fields stay out of the way. `undefined` until
 * the setting loads.
 */
const useRadiusEnabled = (): boolean | undefined => {
  const { data } = useQuery({
    queryKey: ["tacacs_ng_settings"],
    queryFn: () => TacacsNgSettingsService.readTacacsNgSettings(),
    staleTime: 5 * 60 * 1000,
  })
  return data?.radius_enabled
}

export default useRadiusEnabled
