import { Portal, Tooltip as ChakraTooltip } from "@chakra-ui/react"
import * as React from "react"

export interface TooltipProps
  extends React.ComponentProps<typeof ChakraTooltip.Root> {
  showArrow?: boolean
  portalled?: boolean
  content: React.ReactNode
  disabled?: boolean
  placement?: "top" | "bottom" | "left" | "right"
}

export const Tooltip = React.forwardRef<HTMLDivElement, TooltipProps>(
  function Tooltip(props, ref) {
    const {
      showArrow,
      children,
      disabled,
      portalled = true,
      content,
      placement,
      ...rest
    } = props

    if (disabled) return <>{children}</>

    return (
      <ChakraTooltip.Root
        openDelay={300}
        closeDelay={100}
        positioning={placement ? { placement } : undefined}
        {...rest}
      >
        <ChakraTooltip.Trigger asChild>{children}</ChakraTooltip.Trigger>
        <Portal disabled={!portalled}>
          <ChakraTooltip.Positioner>
            <ChakraTooltip.Content ref={ref}>
              {showArrow && (
                <ChakraTooltip.Arrow>
                  <ChakraTooltip.ArrowTip />
                </ChakraTooltip.Arrow>
              )}
              {content}
            </ChakraTooltip.Content>
          </ChakraTooltip.Positioner>
        </Portal>
      </ChakraTooltip.Root>
    )
  },
)
