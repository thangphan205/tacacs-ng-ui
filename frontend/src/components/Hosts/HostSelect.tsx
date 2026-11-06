import {
  Combobox,
  createListCollection,
  HStack,
  Spinner,
  Text,
} from "@chakra-ui/react"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useState } from "react"
import { type HostPublic, HostsService } from "@/client"

const PAGE = 50
const DEBOUNCE_MS = 250

interface HostSelectProps {
  /** Selected host name; "" or undefined means none. */
  value: string | null | undefined
  /** Called with the chosen host name, or "" when cleared. */
  onChange: (name: string) => void
  /** Host to leave out of the options, e.g. the one being edited. */
  excludeId?: string
  placeholder?: string
}

/**
 * Type-to-filter picker over all hosts. Options come from the server's
 * `search` (name, IPv4, IPv6, description), sorted by name, so the list does
 * not depend on loading every host and stays usable with thousands of them.
 */
export function HostSelect({
  value,
  onChange,
  excludeId,
  placeholder = "None — type to search hosts",
}: HostSelectProps) {
  const selected = value || ""
  const [inputValue, setInputValue] = useState(selected)
  const [search, setSearch] = useState("")

  // Follow outside changes, e.g. the form being reset.
  useEffect(() => setInputValue(selected), [selected])

  // While the input still shows the selection, list everything rather than
  // only the hosts matching the selected name.
  const term = inputValue === selected ? "" : inputValue.trim()
  useEffect(() => {
    const t = setTimeout(() => setSearch(term), DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [term])

  const { data, isFetching } = useQuery({
    queryKey: ["hosts", "select", search],
    queryFn: () =>
      HostsService.readHosts({
        search: search || undefined,
        sort_by: "name",
        limit: PAGE,
      }),
    placeholderData: keepPreviousData,
  })

  const collection = useMemo(
    () =>
      createListCollection<HostPublic>({
        items: (data?.data ?? []).filter((h) => h.id !== excludeId),
        itemToValue: (h) => h.name,
        itemToString: (h) => h.name,
      }),
    [data, excludeId],
  )
  const more = (data?.count ?? 0) > PAGE

  return (
    <Combobox.Root
      collection={collection}
      size="sm"
      value={selected ? [selected] : []}
      inputValue={inputValue}
      onInputValueChange={(e) => setInputValue(e.inputValue)}
      onValueChange={(e) => onChange(e.value[0] ?? "")}
      openOnClick
      // Typing a name that is not a host must not stick: the input reverts
      // to the selection when the field loses focus.
      allowCustomValue={false}
      onOpenChange={(e) => {
        if (!e.open) setInputValue(selected)
      }}
    >
      <Combobox.Control>
        <Combobox.Input placeholder={placeholder} />
        <Combobox.IndicatorGroup>
          {isFetching && <Spinner size="xs" color="fg.muted" />}
          <Combobox.ClearTrigger aria-label="Clear parent host" />
          <Combobox.Trigger />
        </Combobox.IndicatorGroup>
      </Combobox.Control>
      <Combobox.Positioner>
        <Combobox.Content maxH="280px">
          <Combobox.Empty>No hosts match “{search}”</Combobox.Empty>
          {collection.items.map((h) => (
            <Combobox.Item item={h} key={h.id}>
              <HStack justify="space-between" flex="1" gap={3} minW={0}>
                <Text truncate>{h.name}</Text>
                {h.ipv4_address && (
                  <Text fontSize="xs" color="fg.muted" fontFamily="mono">
                    {h.ipv4_address}
                  </Text>
                )}
              </HStack>
              <Combobox.ItemIndicator />
            </Combobox.Item>
          ))}
          {more && (
            <Text px={2} py={1.5} fontSize="xs" color="fg.muted">
              Showing the first {PAGE} of {data?.count} — type to narrow
            </Text>
          )}
        </Combobox.Content>
      </Combobox.Positioner>
    </Combobox.Root>
  )
}
