import { Flex, type FlexProps } from "@chakra-ui/react"
import type { ReactNode } from "react"

interface ListToolbarProps extends Omit<FlexProps, "children"> {
  /** Left side: the page's primary action, usually an "Add …" button. */
  actions?: ReactNode
  /** Right side: `SearchBox`, `FilterSelect`s, `RefreshControl`. */
  children?: ReactNode
}

/**
 * The row above every list table. Actions sit left, search and filters
 * right; it wraps on narrow screens with the filters keeping their order.
 */
export function ListToolbar({ actions, children, ...rest }: ListToolbarProps) {
  return (
    <Flex
      mt={6}
      align="center"
      justify="space-between"
      gap={3}
      wrap="wrap"
      {...rest}
    >
      {actions}
      {children && (
        <Flex
          gap={3}
          align="center"
          wrap="wrap"
          ml="auto"
          justify="flex-end"
          flex={{ base: "1 1 100%", md: "0 1 auto" }}
        >
          {children}
        </Flex>
      )}
    </Flex>
  )
}
