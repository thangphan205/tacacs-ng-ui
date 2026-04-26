import { Box, Button, Flex, Spinner, Text } from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { diffLines } from "diff"
import { useEffect, useMemo, useState } from "react"
import { FiGitBranch } from "react-icons/fi"

import { TacacsConfigsService, type TacacsConfigPublic } from "@/client"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog"

interface DiffTacacsConfigProps {
  tacacs_config: TacacsConfigPublic
}

const DiffTacacsConfig = ({ tacacs_config }: DiffTacacsConfigProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [compareId, setCompareId] = useState<string | null>(null)

  const { data: listData } = useQuery({
    queryKey: ["tacacs_configs", "list-all"],
    queryFn: () => TacacsConfigsService.readTacacsConfigs({ skip: 0, limit: 1000 }),
    enabled: isOpen,
  })

  const otherConfigs = useMemo(
    () => (listData?.data ?? []).filter((c) => c.id !== tacacs_config.id),
    [listData, tacacs_config.id],
  )

  useEffect(() => {
    if (!otherConfigs.length || compareId) return
    const active = otherConfigs.find((c) => c.active)
    setCompareId((active ?? otherConfigs[0]).id)
  }, [otherConfigs]) // intentionally omit compareId — only auto-select on first load

  const { data: sourceData, isLoading: sourceLoading } = useQuery({
    queryKey: ["tacacs_config", tacacs_config.id],
    queryFn: () => TacacsConfigsService.readTacacsConfigById({ id: tacacs_config.id }),
    enabled: isOpen,
  })

  const { data: compareData, isLoading: compareLoading } = useQuery({
    queryKey: ["tacacs_config", compareId],
    queryFn: () => TacacsConfigsService.readTacacsConfigById({ id: compareId! }),
    enabled: isOpen && !!compareId,
  })

  const compareConfig = otherConfigs.find((c) => c.id === compareId)

  const changes = useMemo(() => {
    if (!compareData?.data || !sourceData?.data) return []
    return diffLines(compareData.data, sourceData.data)
  }, [compareData, sourceData])

  const renderDiff = () => {
    if (!otherConfigs.length) {
      return (
        <Text color="fg.muted" p={4}>
          No other configurations to compare against.
        </Text>
      )
    }
    if (sourceLoading || compareLoading) return <Spinner m={4} />
    if (!compareData?.data || !sourceData?.data) {
      return (
        <Text color="fg.muted" p={4}>
          Select a configuration to compare.
        </Text>
      )
    }
    if (changes.length === 0) {
      return (
        <Text color="fg.muted" p={4}>
          Files are identical.
        </Text>
      )
    }
    return changes.flatMap((change, i) =>
      change.value
        .split("\n")
        .slice(0, change.value.endsWith("\n") ? -1 : undefined)
        .map((line, j) => (
          <Box
            key={`${i}-${j}`}
            bg={change.added ? "green.subtle" : change.removed ? "red.subtle" : "transparent"}
            color={change.added ? "green.fg" : change.removed ? "red.fg" : "inherit"}
            fontFamily="mono"
            fontSize="xs"
            px={4}
            lineHeight="1.5"
            whiteSpace="pre"
          >
            {change.added ? "+" : change.removed ? "-" : " "}
            {line}
          </Box>
        )),
    )
  }

  return (
    <DialogRoot
      size={{ base: "xl", md: "xl" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="ghost">
          <FiGitBranch fontSize="16px" />
          Compare
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Compare Configs</DialogTitle>
        </DialogHeader>
        <DialogBody>
          {otherConfigs.length > 0 && (
            <>
              <Flex align="center" gap={2} mb={3}>
                <Text fontSize="sm" color="fg.muted" flexShrink={0}>
                  Compare against:
                </Text>
                <select
                  value={compareId ?? ""}
                  onChange={(e) => setCompareId(e.target.value)}
                  style={{
                    fontSize: "0.875rem",
                    padding: "4px 8px",
                    borderRadius: "6px",
                    flex: 1,
                    border: "1px solid var(--chakra-colors-border)",
                    background: "var(--chakra-colors-bg)",
                    color: "inherit",
                  }}
                >
                  {otherConfigs.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.filename}
                      {c.active ? " (Active)" : ""}
                    </option>
                  ))}
                </select>
              </Flex>
              <Flex justify="space-between" mb={1} px={4}>
                <Text fontFamily="mono" fontSize="xs" color="red.fg">
                  --- {compareConfig?.filename ?? ""}
                </Text>
                <Text fontFamily="mono" fontSize="xs" color="green.fg">
                  +++ {tacacs_config.filename}
                </Text>
              </Flex>
            </>
          )}
          <Box maxH="500px" overflowY="auto" borderWidth="1px" borderRadius="md">
            {renderDiff()}
          </Box>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setIsOpen(false)}>
            Close
          </Button>
        </DialogFooter>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default DiffTacacsConfig
