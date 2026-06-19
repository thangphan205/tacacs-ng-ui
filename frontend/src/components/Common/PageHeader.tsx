import { Box, Flex, Heading, HStack, Text, VStack } from "@chakra-ui/react"
import type { IconType } from "react-icons"

interface PageHeaderProps {
  title: string
  description?: string
  icon: IconType
}

export const PageHeader = ({
  title,
  description,
  icon: Icon,
}: PageHeaderProps) => {
  return (
    <Flex direction="column" pt={6} gap={1}>
      <HStack gap={3}>
        <Box p={2} bg="teal.muted" borderRadius="lg" color="teal.fg">
          <Icon fontSize="22px" />
        </Box>
        <VStack align="start" gap={0}>
          <Heading size="md">{title}</Heading>
          {description && (
            <Text color="fg.muted" fontSize="xs">
              {description}
            </Text>
          )}
        </VStack>
      </HStack>
    </Flex>
  )
}

export default PageHeader
