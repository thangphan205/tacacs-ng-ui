import {
  Badge,
  Button,
  DialogTitle,
  Icon,
  Link,
  Table,
  Tabs,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { FiBook, FiCheck, FiExternalLink, FiPlus } from "react-icons/fi"

import { MavisesService } from "@/client"
import type { ApiError } from "@/client/core/ApiError"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogHeader,
  DialogRoot,
  DialogTrigger,
} from "../ui/dialog"
import { MAVIS_TEMPLATES, type MavisTemplateEntry } from "./mavisTemplates"

const LoadMavisTemplate = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [addingKey, setAddingKey] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()

  const { data: existingMavises } = useQuery({
    queryKey: ["mavises-all"],
    queryFn: () => MavisesService.readMavises({ limit: 200 }),
    enabled: isOpen,
  })

  const existingKeys = new Set(
    existingMavises?.data.map((m) => m.mavis_key) ?? [],
  )

  const mutation = useMutation({
    mutationFn: (entry: MavisTemplateEntry) =>
      MavisesService.createMavis({
        requestBody: {
          mavis_key: entry.mavis_key,
          mavis_value: entry.mavis_value,
        },
      }),
    onSuccess: (_, entry) => {
      showSuccessToast(`${entry.mavis_key} added.`)
      queryClient.invalidateQueries({ queryKey: ["mavises"] })
      queryClient.invalidateQueries({ queryKey: ["mavises-all"] })
    },
    onError: (err: ApiError) => handleError(err),
    onSettled: () => setAddingKey(null),
  })

  const handleAdd = (entry: MavisTemplateEntry) => {
    setAddingKey(entry.mavis_key)
    mutation.mutate(entry)
  }

  return (
    <DialogRoot
      size={{ base: "xs", md: "xl" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        <Button my={4} variant="subtle">
          <FiBook fontSize="16px" />
          Configure Guide
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>LDAP Backend Configuration Guide</DialogTitle>
        </DialogHeader>
        <DialogBody pb={6}>
          <Text mb={4} color="fg.muted" fontSize="sm">
            Reference for MAVIS LDAP environment variables. Click{" "}
            <Badge variant="subtle" colorPalette="blue" fontSize="xs">
              Add
            </Badge>{" "}
            to insert a key with its default value.{" "}
            <Link
              href="https://projects.pro-bono-publico.de/event-driven-servers/doc/tac_plus-ng.html#AEN3284"
              target="_blank"
              rel="noopener noreferrer"
              color="blue.500"
            >
              Full documentation{" "}
              <FiExternalLink
                style={{ display: "inline", verticalAlign: "middle" }}
              />
            </Link>
          </Text>
          <Tabs.Root defaultValue={MAVIS_TEMPLATES[0].id} variant="subtle">
            <Tabs.List>
              {MAVIS_TEMPLATES.map((t) => (
                <Tabs.Trigger key={t.id} value={t.id}>
                  {t.label}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
            {MAVIS_TEMPLATES.map((t) => (
              <Tabs.Content key={t.id} value={t.id}>
                <VStack align="stretch" gap={3} pt={3}>
                  <Text fontSize="sm" color="fg.muted">
                    {t.description}
                  </Text>
                  <Table.Root size="sm">
                    <Table.Header>
                      <Table.Row>
                        <Table.ColumnHeader>Key</Table.ColumnHeader>
                        <Table.ColumnHeader>Example Value</Table.ColumnHeader>
                        <Table.ColumnHeader>Description</Table.ColumnHeader>
                        <Table.ColumnHeader w="16" />
                      </Table.Row>
                    </Table.Header>
                    <Table.Body>
                      {t.entries.map((entry) => {
                        const exists = existingKeys.has(entry.mavis_key)
                        return (
                          <Table.Row key={entry.mavis_key}>
                            <Table.Cell fontFamily="mono" whiteSpace="nowrap">
                              {entry.mavis_key}
                            </Table.Cell>
                            <Table.Cell
                              fontFamily="mono"
                              fontSize="xs"
                              color="fg.muted"
                              maxW="2xs"
                              truncate
                            >
                              {entry.mavis_value}
                            </Table.Cell>
                            <Table.Cell fontSize="sm">
                              {entry.description}
                            </Table.Cell>
                            <Table.Cell>
                              {exists ? (
                                <Icon color="green.500" fontSize="md">
                                  <FiCheck />
                                </Icon>
                              ) : (
                                <Button
                                  size="xs"
                                  variant="ghost"
                                  colorPalette="blue"
                                  loading={addingKey === entry.mavis_key}
                                  onClick={() => handleAdd(entry)}
                                  aria-label={`Add ${entry.mavis_key}`}
                                >
                                  <FiPlus />
                                  Add
                                </Button>
                              )}
                            </Table.Cell>
                          </Table.Row>
                        )
                      })}
                    </Table.Body>
                  </Table.Root>
                </VStack>
              </Tabs.Content>
            ))}
          </Tabs.Root>
        </DialogBody>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default LoadMavisTemplate
