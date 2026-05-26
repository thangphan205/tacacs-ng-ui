import { createListCollection, Flex, Select, Text } from "@chakra-ui/react"

function defaultOptions(value: number): number[] {
  if (value <= 5) return [5, 10, 50]
  return [10, 50, 100, 200]
}

interface PageSizeSelectProps {
  value: number
  onChange: (n: number) => void
  options?: number[]
}

export function PageSizeSelect({
  value,
  onChange,
  options,
}: PageSizeSelectProps) {
  const sizes = options ?? defaultOptions(value)
  const collection = createListCollection({
    items: sizes.map((n) => ({ value: String(n) })),
  })

  return (
    <Flex align="center" gap={2}>
      <Text fontSize="xs" color="fg.muted" flexShrink={0}>
        Rows per page
      </Text>
      <Select.Root
        collection={collection}
        value={[String(value)]}
        onValueChange={({ value: v }) => onChange(Number(v[0]))}
        size="sm"
        width="auto"
      >
        <Select.Control>
          <Select.Trigger minW="90px" whiteSpace="nowrap">
            <Select.ValueText />
          </Select.Trigger>
          <Select.IndicatorGroup>
            <Select.Indicator />
          </Select.IndicatorGroup>
        </Select.Control>
        <Select.Positioner>
          <Select.Content minW="110px">
            <Select.ItemGroup>
              {collection.items.map((item) => (
                <Select.Item
                  key={item.value}
                  item={item.value}
                  whiteSpace="nowrap"
                >
                  {item.value}
                  <Select.ItemIndicator />
                </Select.Item>
              ))}
            </Select.ItemGroup>
          </Select.Content>
        </Select.Positioner>
      </Select.Root>
    </Flex>
  )
}
