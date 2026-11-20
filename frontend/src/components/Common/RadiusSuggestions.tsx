import useRadiusEnabled from "@/hooks/useRadiusEnabled"

/**
 * Browser autocomplete for RADIUS keys in profile scripts. Rendered only while
 * RADIUS is enabled; inputs point at the lists with `list={RADIUS_LISTS.…}`
 * and simply get no suggestions otherwise.
 */
export const RADIUS_LISTS = {
  scriptKeys: "radius-script-keys",
  scriptValues: "radius-script-values",
  setKeys: "radius-set-keys",
} as const

// Attributes from the built-in dictionary (backend/app/core/radius_dictionary.cfg).
const SET_KEYS = [
  "radius[MikroTik:MikroTik-Group]",
  "radius[Cisco:Cisco-AVPair]",
  "radius[Fortinet:Fortinet-Access-Profile]",
  "radius[Fortinet:Fortinet-Group-Name]",
  "radius[PaloAlto:PaloAlto-Admin-Role]",
  "radius[Juniper:Juniper-Local-User-Name]",
  "radius[Aruba:Aruba-Admin-Role]",
  "radius[Huawei:Huawei-Exec-Privilege]",
  "radius[Reply-Message]",
  "radius[Session-Timeout]",
]

export function RadiusSuggestions() {
  const radiusEnabled = useRadiusEnabled()
  if (!radiusEnabled) return null
  return (
    <>
      <datalist id={RADIUS_LISTS.scriptKeys}>
        <option value="aaa.protocol" />
        <option value="radius[Service-Type]" />
        <option value="radius[NAS-Identifier]" />
      </datalist>
      <datalist id={RADIUS_LISTS.scriptValues}>
        <option value="radius" />
        <option value="tacacs" />
        <option value="Administrative-User" />
        <option value="NAS-Prompt-User" />
        <option value="Login-User" />
      </datalist>
      <datalist id={RADIUS_LISTS.setKeys}>
        {SET_KEYS.map((key) => (
          <option key={key} value={key} />
        ))}
      </datalist>
    </>
  )
}
