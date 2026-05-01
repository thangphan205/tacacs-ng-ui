import { Box, Button, Flex, Spinner, Text } from "@chakra-ui/react"
import { useQuery } from "@tanstack/react-query"
import { diffLines } from "diff"
import { useMemo, useState } from "react"
import { FiGitBranch } from "react-icons/fi"

import { TacacsConfigsService } from "@/client"
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

const selectStyle: React.CSSProperties = {
  fontSize: "0.875rem",
  padding: "4px 8px",
  borderRadius: "6px",
  flex: 1,
  border: "1px solid var(--chakra-colors-border)",
  background: "var(--chakra-colors-bg)",
  color: "inherit",
}

const CompareConfigs = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [configAId, setConfigAId] = useState<string | null>(null)
  const [configBId, setConfigBId] = useState<string | null>(null)

  const { data: listData } = useQuery({
    queryKey: ["tacacs_configs", "list-all"],
    queryFn: () =>
      TacacsConfigsService.readTacacsConfigs({ skip: 0, limit: 1000 }),
    enabled: isOpen,
  })

  const configs = useMemo(() => listData?.data ?? [], [listData])

  // Auto-select on first load
  useMemo(() => {
    if (!configs.length) return
    if (!configAId) {
      const active = configs.find((c) => c.active)
      setConfigAId((active ?? configs[0]).id)
    }
    if (!configBId) {
      const others = configs.filter((c) => c.id !== configAId)
      if (others.length) setConfigBId(others[0].id)
    }
  }, [configs]) // eslint-disable-line react-hooks/exhaustive-deps

  const { data: dataA, isLoading: loadingA } = useQuery({
    queryKey: ["tacacs_config", configAId],
    queryFn: () =>
      TacacsConfigsService.readTacacsConfigById({ id: configAId! }),
    enabled: isOpen && !!configAId,
  })

  const { data: dataB, isLoading: loadingB } = useQuery({
    queryKey: ["tacacs_config", configBId],
    queryFn: () =>
      TacacsConfigsService.readTacacsConfigById({ id: configBId! }),
    enabled: isOpen && !!configBId,
  })

  const configA = configs.find((c) => c.id === configAId)
  const configB = configs.find((c) => c.id === configBId)

  const changes = useMemo(() => {
    if (!dataA?.data || !dataB?.data) return []
    return diffLines(dataA.data, dataB.data)
  }, [dataA, dataB])

  const renderDiff = () => {
    if (configs.length < 2) {
      return (
        <Text color="fg.muted" p={4}>
          Need at least two configurations to compare.
        </Text>
      )
    }
    if (configAId === configBId) {
      return (
        <Text color="fg.muted" p={4}>
          Select two different configurations to compare.
        </Text>
      )
    }
    if (loadingA || loadingB) return <Spinner m={4} />
    if (!dataA?.data || !dataB?.data) {
      return (
        <Text color="fg.muted" p={4}>
          Could not load configuration data.
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
            bg={
              change.added
                ? "green.subtle"
                : change.removed
                  ? "red.subtle"
                  : "transparent"
            }
            color={
              change.added ? "green.fg" : change.removed ? "red.fg" : "inherit"
            }
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
    <Box display="contents">
    <DialogRoot
      size={{ base: "xl", md: "xl" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button variant="solid" my={4}>
          <FiGitBranch fontSize="16px" />
          Compare Configs
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Compare Configurations</DialogTitle>
        </DialogHeader>
        <DialogBody>
          {configs.length >= 2 && (
            <>
              <Flex align="center" gap={2} mb={2}>
                <Text fontSize="sm" color="fg.muted" flexShrink={0} w="60px">
                  Config A:
                </Text>
                <select
                  value={configAId ?? ""}
                  onChange={(e) => setConfigAId(e.target.value)}
                  style={selectStyle}
                >
                  {configs.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.filename}
                      {c.active ? " (Active)" : ""}
                    </option>
                  ))}
                </select>
              </Flex>
              <Flex align="center" gap={2} mb={3}>
                <Text fontSize="sm" color="fg.muted" flexShrink={0} w="60px">
                  Config B:
                </Text>
                <select
                  value={configBId ?? ""}
                  onChange={(e) => setConfigBId(e.target.value)}
                  style={selectStyle}
                >
                  {configs.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.filename}
                      {c.active ? " (Active)" : ""}
                    </option>
                  ))}
                </select>
              </Flex>
              {configAId !== configBId && (
                <Flex justify="space-between" mb={1} px={4}>
                  <Text fontFamily="mono" fontSize="xs" color="red.fg">
                    --- {configA?.filename ?? ""}
                  </Text>
                  <Text fontFamily="mono" fontSize="xs" color="green.fg">
                    +++ {configB?.filename ?? ""}
                  </Text>
                </Flex>
              )}
            </>
          )}
          <Box
            maxH="500px"
            overflowY="auto"
            borderWidth="1px"
            borderRadius="md"
          >
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
    </Box>
  )
}

export default CompareConfigs
