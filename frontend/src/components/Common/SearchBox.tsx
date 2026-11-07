import { Input } from "@chakra-ui/react"
import { useEffect, useRef, useState } from "react"
import { FiSearch } from "react-icons/fi"
import { CloseButton } from "@/components/ui/close-button"
import { InputGroup } from "@/components/ui/input-group"

const DEBOUNCE_MS = 500

interface SearchBoxProps {
  /** Current committed value; a change from outside (URL, a badge click) replaces the text. */
  initialValue?: string
  onSearch: (value: string) => void
  placeholder?: string
  ariaLabel?: string
  maxW?: string
}

/**
 * The one free-text search input for list pages: search icon, clear button,
 * and a debounced `onSearch`. Clearing commits at once, without the delay.
 */
export const SearchBox = ({
  initialValue = "",
  onSearch,
  placeholder = "Search...",
  ariaLabel,
  maxW = "md",
}: SearchBoxProps) => {
  const [localSearch, setLocalSearch] = useState(initialValue)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setLocalSearch(initialValue)
  }, [initialValue])

  // A pending commit must not fire after the page using it has unmounted.
  useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    },
    [],
  )

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setLocalSearch(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      onSearch(val)
    }, DEBOUNCE_MS)
  }

  const handleClear = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    setLocalSearch("")
    onSearch("")
  }

  return (
    <InputGroup
      maxW={maxW}
      flex="1"
      minW="200px"
      startElement={<FiSearch />}
      endElement={
        localSearch ? (
          <CloseButton
            size="xs"
            onClick={handleClear}
            aria-label="Clear search"
          />
        ) : undefined
      }
    >
      <Input
        type="text"
        placeholder={placeholder}
        aria-label={ariaLabel ?? placeholder}
        value={localSearch}
        onChange={handleSearchChange}
        size="sm"
      />
    </InputGroup>
  )
}
