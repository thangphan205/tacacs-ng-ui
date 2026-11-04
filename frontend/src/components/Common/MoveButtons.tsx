import { IconButton } from "@chakra-ui/react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { FiArrowDown, FiArrowUp } from "react-icons/fi"

import type { ApiError } from "@/api"
import { Tooltip } from "@/components/ui/tooltip"
import { handleError } from "@/utils"

interface MoveButtonsProps {
  /** 0-based index of the row in the list as displayed. */
  index: number
  /** Number of rows in the list. */
  count: number
  /** What is being moved, for the accessible labels ("script", "rule"). */
  noun: string
  /** Persist the row at the given 0-based position. */
  onMove: (position: number) => Promise<unknown>
}

/**
 * Up/down reorder buttons for rows whose order tac_plus-ng evaluates top to
 * bottom (profile scripts, ruleset scripts, rulesets). The server renumbers
 * the siblings and refuses a move that would orphan an `elif` / `else`.
 */
const MoveButtons = ({ index, count, noun, onMove }: MoveButtonsProps) => {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: onMove,
    onError: (err: ApiError) => handleError(err),
    onSettled: () => {
      queryClient.invalidateQueries()
    },
  })

  return (
    <>
      <Tooltip content={`Move ${noun} up`} showArrow>
        <IconButton
          size="xs"
          variant="ghost"
          aria-label={`Move ${noun} up`}
          disabled={index === 0 || mutation.isPending}
          onClick={() => mutation.mutate(index - 1)}
        >
          <FiArrowUp />
        </IconButton>
      </Tooltip>
      <Tooltip content={`Move ${noun} down`} showArrow>
        <IconButton
          size="xs"
          variant="ghost"
          aria-label={`Move ${noun} down`}
          disabled={index >= count - 1 || mutation.isPending}
          onClick={() => mutation.mutate(index + 1)}
        >
          <FiArrowDown />
        </IconButton>
      </Tooltip>
    </>
  )
}

export default MoveButtons
