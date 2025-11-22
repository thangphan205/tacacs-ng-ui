import {
  Button,
  ButtonGroup,
  Code,
  Spinner,
  Text,
  VStack,
  Table,
} from "@chakra-ui/react"
import { useQuery, } from "@tanstack/react-query"
import { useState } from "react"
import { FaEye } from "react-icons/fa"
import React from "react"
import {
  TacacsLogsService,
} from "@/client"


import {
  DialogActionTrigger,
  DialogBody,
  DialogCloseTrigger,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogRoot,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog"

interface ShowTacacsLogProps {
  tacacs_log: any
  children?: React.ReactNode
}

const ShowTacacsLog = ({
  tacacs_log,
  children,
}: ShowTacacsLogProps) => {
  const [isOpen, setIsOpen] = useState(false)


  const { data, isLoading, error } = useQuery({
    queryKey: ["tacacs_log", tacacs_log.id],
    queryFn: () => TacacsLogsService.readLogFile({ id: tacacs_log.id }),
    enabled: isOpen, // Only fetch when the dialog is open
  })



  const renderContent = () => {
    if (isLoading) {
      return <Spinner />
    }
    if (error) {
      return <Text color="red.500">Error loading configuration.</Text>
    }
    if (data?.data) {
      const logLines = data.data.trim().split("\n").map(line => line.split("\t"));

      return (

        <Table.Root size="sm">

          <Table.Body>
            {logLines.map((line, rowIndex) => (
              <Table.Row key={rowIndex}>
                {line.map((cell, cellIndex) => <Table.Cell key={cellIndex}>{cell}</Table.Cell>)}
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      )
    }
    return <Text>No content available.</Text>
  }

  return (
    <DialogRoot
      size={{ base: "md", md: "xl" }}
      placement="center"
      open={isOpen}
      onOpenChange={({ open }) => setIsOpen(open)}
    >
      <DialogTrigger asChild>
        {children || (
          <Button variant="ghost">
            <FaEye fontSize="16px" />
            Show Config
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Configuration for: <Code>{tacacs_log.filename}</Code>
          </DialogTitle>
        </DialogHeader>
        <DialogBody>
          <VStack gap={4} align="stretch">
            {renderContent()}
          </VStack>
        </DialogBody>
        <DialogFooter gap={2}>
          <ButtonGroup>
            <DialogActionTrigger asChild>
              <Button
                variant="subtle"
                colorPalette="gray"
              >
                Cancel
              </Button>
            </DialogActionTrigger>

          </ButtonGroup>
        </DialogFooter>
        <DialogCloseTrigger />
      </DialogContent>
    </DialogRoot>
  )
}

export default ShowTacacsLog
