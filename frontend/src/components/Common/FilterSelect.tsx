import { createListCollection, Portal, Select } from "@chakra-ui/react"
import { useMemo } from "react"

export interface FilterOption {
  value: string
  label: string
}

interface FilterSelectProps {
  /** Selected option; `undefined` means no filter ("all"). */
  value: string | undefined
  onChange: (value: string | undefined) => void
  /** The real choices only — "all" is the empty state, not an option. */
  options: FilterOption[]
  /** Shown when nothing is selected, e.g. "All statuses". */
  placeholder: string
  ariaLabel?: string
  /** Fixed so the toolbar does not jump as the selected label changes. */
  width?: string
}

/**
 * The one dropdown filter for list toolbars. Same size as `SearchBox`;
 * the clear trigger returns to "all".
 */
export function FilterSelect({
  value,
  onChange,
  options,
  placeholder,
  ariaLabel,
  width = "180px",
}: FilterSelectProps) {
  const collection = useMemo(
    () => createListCollection({ items: options }),
    [options],
  )

  return (
    <Select.Root
      collection={collection}
      value={value ? [value] : []}
      onValueChange={({ value: v }) => onChange(v[0] || undefined)}
      size="sm"
      width={width}
    >
      <Select.HiddenSelect />
      <Select.Control>
        <Select.Trigger
          aria-label={ariaLabel ?? placeholder}
          // Room for the clear button next to the chevron.
          pe={value ? "14" : undefined}
        >
          <Select.ValueText placeholder={placeholder} />
        </Select.Trigger>
        <Select.IndicatorGroup>
          {value && <Select.ClearTrigger aria-label={`Clear ${placeholder}`} />}
          <Select.Indicator />
        </Select.IndicatorGroup>
      </Select.Control>
      <Portal>
        <Select.Positioner>
          <Select.Content>
            {collection.items.map((item) => (
              <Select.Item key={item.value} item={item}>
                {item.label}
                <Select.ItemIndicator />
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Positioner>
      </Portal>
    </Select.Root>
  )
}
