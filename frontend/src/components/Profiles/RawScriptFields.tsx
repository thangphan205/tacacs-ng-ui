import { Button, ButtonGroup, Flex, Text, Textarea } from "@chakra-ui/react"
import { useMutation } from "@tanstack/react-query"
import type { KeyboardEvent } from "react"
import type { UseFormRegisterReturn } from "react-hook-form"
import { FiCheckCircle, FiCode, FiList, FiXCircle } from "react-icons/fi"

import { ApiError } from "@/api"
import { type ProfileRawCheckResult, ProfilesService } from "@/client"
import { handleError } from "@/utils"
import { Field } from "../ui/field"

export type ScriptMode = "structured" | "raw"

interface RawScriptFieldsProps {
  mode: ScriptMode
  onModeChange: (mode: ScriptMode) => void
  /** Why raw mode is unavailable (a profile with structured scripts). */
  rawDisabledReason?: string
  /** Shown under the toggle while switching a saved raw profile back. */
  clearingRaw?: boolean
  register: UseFormRegisterReturn
  error?: string
  /** Current name, id and text, for the tac_plus-ng check. */
  checkInput: () => { id?: string; name: string; raw_script: string }
}

/**
 * Structured / raw toggle and the raw-script editor (#359). The raw text is
 * the profile's `script { }` body; the generator writes the wrappers.
 */
export function RawScriptFields({
  mode,
  onModeChange,
  rawDisabledReason,
  clearingRaw,
  register,
  error,
  checkInput,
}: RawScriptFieldsProps) {
  const check = useMutation({
    mutationFn: () =>
      ProfilesService.checkProfileRawScript({ profileRawCheck: checkInput() }),
    onError: (err: ApiError) => {
      // 422 = the text failed the wrapper checks; shown inline below.
      if (err.status !== 422) handleError(err)
    },
  })

  // Tab indents instead of leaving the field.
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== "Tab" || e.shiftKey) return
    e.preventDefault()
    const el = e.currentTarget
    el.setRangeText("    ", el.selectionStart, el.selectionEnd, "end")
    el.dispatchEvent(new Event("input", { bubbles: true }))
  }

  const checkError =
    check.error instanceof ApiError && check.error.status === 422
      ? String((check.error.body as { detail?: unknown })?.detail ?? "")
      : undefined

  return (
    <>
      {/* Outside a Field: its context would label the buttons as the field. */}
      <Flex direction="column" gap={1.5} w="full">
        <Text fontSize="sm" fontWeight="medium">
          Script mode
        </Text>
        <ButtonGroup size="sm" variant="outline" attached>
          <Button
            type="button"
            aria-pressed={mode === "structured"}
            variant={mode === "structured" ? "solid" : "outline"}
            colorPalette="teal"
            onClick={() => onModeChange("structured")}
          >
            <FiList /> Structured
          </Button>
          <Button
            type="button"
            aria-pressed={mode === "raw"}
            variant={mode === "raw" ? "solid" : "outline"}
            colorPalette="teal"
            disabled={!!rawDisabledReason}
            title={rawDisabledReason}
            onClick={() => onModeChange("raw")}
          >
            <FiCode /> Raw script
          </Button>
        </ButtonGroup>
        {rawDisabledReason && (
          <Text fontSize="xs" color="fg.muted">
            {rawDisabledReason}
          </Text>
        )}
        {clearingRaw && (
          <Text fontSize="xs" color="orange.fg">
            Saving removes this profile's raw script.
          </Text>
        )}
      </Flex>

      {mode === "raw" && (
        <Flex direction="column" w="full" gap={2}>
          <Field
            required
            invalid={!!error}
            errorText={error}
            label="Raw script"
            helperText="The body of script { }: the generator writes profile <name> { script { … } } around it. End with your own permit or deny."
          >
            <Textarea
              {...register}
              onChange={(e) => {
                register.onChange(e)
                // An old result no longer describes the text.
                if (!check.isIdle) check.reset()
              }}
              onKeyDown={onKeyDown}
              fontFamily="mono"
              fontSize="xs"
              rows={16}
              spellCheck={false}
              autoComplete="off"
              wrap="off"
              placeholder={
                "if (service == shell) {\n    if (cmd =~ /^show(\\s|$)/) permit\n    deny\n}\ndeny"
              }
            />
          </Field>
          <Flex align="center" gap={3} wrap="wrap">
            <Button
              type="button"
              size="xs"
              variant="outline"
              onClick={() => check.mutate()}
              loading={check.isPending}
            >
              Check with tac_plus-ng
            </Button>
            <CheckResult
              result={check.isSuccess ? check.data : undefined}
              error={checkError}
            />
          </Flex>
        </Flex>
      )}
    </>
  )
}

function CheckResult({
  result,
  error,
}: {
  result?: ProfileRawCheckResult
  error?: string
}) {
  if (error)
    return (
      <Text
        fontSize="xs"
        color="red.fg"
        display="flex"
        gap={1}
        alignItems="center"
      >
        <FiXCircle /> {error}
      </Text>
    )
  if (!result) return null
  if (result.status === "success")
    return (
      <Text
        fontSize="xs"
        color="green.fg"
        display="flex"
        gap={1}
        alignItems="center"
      >
        <FiCheckCircle /> The full config passes tac_plus-ng -P.
      </Text>
    )
  // tac_plus-ng reports where it stopped, which can be a line before the
  // token it rejected; hence "near".
  const where = result.script_line
    ? `Near line ${result.script_line} of the script`
    : result.line
      ? `Line ${result.line} of the full config (outside this script)`
      : "tac_plus-ng"
  return (
    <Text
      fontSize="xs"
      color="red.fg"
      display="flex"
      gap={1}
      alignItems="center"
    >
      <FiXCircle /> {where}: {result.message}
    </Text>
  )
}
