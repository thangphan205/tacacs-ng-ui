import { Button, IconButton } from "@chakra-ui/react"
import { useMutation } from "@tanstack/react-query"
import { FaDownload } from "react-icons/fa"

import type { ApiError } from "@/api"
import { type TacacsLogPublic, TacacsLogsService } from "@/client"
import { handleError } from "@/utils"

type LogRef = Pick<TacacsLogPublic, "id" | "filename">

/**
 * Fetch the raw file and hand it to the browser as a download. A plain link
 * would not carry the bearer token, which lives in localStorage.
 */
async function downloadTacacsLog(log: LogRef): Promise<void> {
  const body = await TacacsLogsService.downloadLogFile(
    { id: log.id },
    { parseAs: "blob" },
  )
  const blob =
    body instanceof Blob
      ? body
      : new Blob([String(body)], { type: "text/plain" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = log.filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  // Revoking in the same tick can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

interface DownloadTacacsLogButtonProps {
  log: LogRef
  /** Icon-only for table rows; labelled button in the dialog footer. */
  iconOnly?: boolean
}

export function DownloadTacacsLogButton({
  log,
  iconOnly = false,
}: DownloadTacacsLogButtonProps) {
  const mutation = useMutation({
    mutationFn: () => downloadTacacsLog(log),
    onError: (err: ApiError) => handleError(err),
  })

  if (iconOnly) {
    return (
      <IconButton
        aria-label={`Download ${log.filename}`}
        title={`Download ${log.filename}`}
        variant="ghost"
        size="sm"
        loading={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        <FaDownload />
      </IconButton>
    )
  }
  return (
    <Button
      variant="subtle"
      loading={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      <FaDownload />
      Download
    </Button>
  )
}
