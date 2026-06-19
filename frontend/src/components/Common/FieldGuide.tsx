import { Badge, Box, Flex, Text, VStack } from "@chakra-ui/react"
import type React from "react"
import { FiLock } from "react-icons/fi"

export interface FieldGuideItem {
  icon: React.ElementType
  label: string
  description: string
  example?: string
  required?: boolean
}

const FieldGuideCard = ({ item }: { item: FieldGuideItem }) => {
  const Icon = item.icon
  return (
    <Box>
      <Flex align="flex-start" gap={2.5}>
        <Box
          mt={0.5}
          p={1}
          bg="teal.muted"
          color="teal.fg"
          borderRadius="md"
          flexShrink={0}
        >
          <Icon size={12} />
        </Box>
        <Box>
          <Flex align="center" gap={1.5} mb={0.5}>
            <Text fontSize="xs" fontWeight="semibold" color="fg">
              {item.label}
            </Text>
            {item.required && (
              <Badge
                colorPalette="red"
                variant="subtle"
                size="sm"
                fontSize="2xs"
                px={1}
                lineHeight="1.4"
              >
                Required
              </Badge>
            )}
          </Flex>
          <Text fontSize="xs" color="fg.muted" lineHeight="1.5">
            {item.description}
          </Text>
          {item.example && (
            <Text fontSize="2xs" color="fg.muted/70" mt={0.5} fontFamily="mono">
              e.g. {item.example}
            </Text>
          )}
        </Box>
      </Flex>
    </Box>
  )
}

interface FieldGuideProps {
  items: FieldGuideItem[]
  icon: React.ElementType
  title?: string
  subtitle?: string
  howItWorks?: string
}

const FieldGuide = ({
  items,
  icon: TitleIcon,
  title = "Field Guide",
  subtitle = "Learn what each field means and how it maps to the configuration.",
  howItWorks,
}: FieldGuideProps) => {
  return (
    <Box
      bg="bg.muted/60"
      p={5}
      borderRadius="xl"
      borderWidth="1px"
      borderColor="border.subtle"
      height="fit-content"
    >
      <Flex align="center" gap={2} mb={1}>
        <Box p={1.5} bg="teal.muted" color="teal.fg" borderRadius="md">
          <TitleIcon size={16} />
        </Box>
        <Text
          fontSize="xs"
          fontWeight="bold"
          textTransform="uppercase"
          letterSpacing="wider"
          color="teal.fg"
        >
          {title}
        </Text>
      </Flex>
      <Text fontSize="xs" color="fg.muted" mb={4}>
        {subtitle}
      </Text>

      <VStack gap={3.5} align="stretch">
        {items.map((item) => (
          <FieldGuideCard key={item.label} item={item} />
        ))}
      </VStack>

      {howItWorks && (
        <Box
          mt={4}
          p={3}
          bg="teal.muted/40"
          borderRadius="md"
          borderWidth="1px"
          borderColor="teal.muted"
        >
          <Flex align="center" gap={1.5} mb={1}>
            <FiLock size={11} />
            <Text fontSize="2xs" fontWeight="semibold" color="teal.fg">
              How it works
            </Text>
          </Flex>
          <Text fontSize="2xs" color="fg.muted" lineHeight="1.5">
            {howItWorks}
          </Text>
        </Box>
      )}
    </Box>
  )
}

export default FieldGuide
