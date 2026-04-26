import { Input } from "@chakra-ui/react"
import { useEffect, useRef, useState } from "react"
import { InputGroup } from "@/components/ui/input-group"

interface SearchBoxProps {
  initialValue?: string
  onSearch: (value: string) => void
  placeholder?: string
}

export const SearchBox = ({
  initialValue = "",
  onSearch,
  placeholder = "Search...",
}: SearchBoxProps) => {
  const [localSearch, setLocalSearch] = useState(initialValue)
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    setLocalSearch(initialValue)
  }, [initialValue])

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      onSearch(val)
    }, 500)
  }

  return (
    <InputGroup maxW="md">
      <Input
        type="text"
        placeholder={placeholder}
        value={localSearch}
        onChange={handleSearchChange}
        size="sm"
      />
    </InputGroup>
  )
}
