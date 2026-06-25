import { Badge, Box, Flex, Text, VStack } from "@chakra-ui/react"
import type React from "react"
import { useState } from "react"
import { FiChevronDown, FiChevronUp, FiLock } from "react-icons/fi"

export interface FieldGuideItem {
  icon: React.ElementType
  label: string
  description: string
  example?: string
  required?: boolean
}

const FieldGuideCard = ({
  item,
  isOpen,
  onToggle,
}: {
  item: FieldGuideItem
  isOpen: boolean
  onToggle: () => void
}) => {
  const Icon = item.icon
  return (
    <Box
      onClick={onToggle}
      cursor="pointer"
      p={2.5}
      borderRadius="lg"
      transition="all 0.2s ease-in-out"
      _hover={{ bg: "bg.muted/90", borderColor: "border.subtle" }}
      borderWidth="1px"
      borderColor={isOpen ? "teal.muted" : "transparent"}
      bg={isOpen ? "bg.muted/50" : "transparent"}
    >
      <Flex align="flex-start" gap={2.5} width="100%">
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
        <Box flex="1" minWidth="0">
          <Flex align="center" justify="space-between" width="100%" gap={2}>
            <Flex align="center" gap={1.5} flexWrap="wrap">
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
            <Box color="fg.muted" flexShrink={0}>
              {isOpen ? <FiChevronUp size={14} /> : <FiChevronDown size={14} />}
            </Box>
          </Flex>
          {isOpen && (
            <Box mt={2}>
              <Text fontSize="xs" color="fg.muted" lineHeight="1.5">
                {item.description}
              </Text>
              {item.example && (
                <Text
                  fontSize="2xs"
                  color="fg.muted/70"
                  mt={1.5}
                  fontFamily="mono"
                >
                  e.g. {item.example}
                </Text>
              )}
            </Box>
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
  // Initialize with the first item expanded by default
  const [expandedLabels, setExpandedLabels] = useState<Record<string, boolean>>(
    () => {
      if (items.length > 0) {
        return { [items[0].label]: true }
      }
      return {}
    },
  )

  const toggleItem = (label: string) => {
    setExpandedLabels((prev) => ({
      ...prev,
      [label]: !prev[label],
    }))
  }

  const isAllExpanded = items.every((item) => expandedLabels[item.label])

  const toggleAll = () => {
    if (isAllExpanded) {
      setExpandedLabels({})
    } else {
      const allExpanded = items.reduce(
        (acc, item) => {
          acc[item.label] = true
          return acc
        },
        {} as Record<string, boolean>,
      )
      setExpandedLabels(allExpanded)
    }
  }

  return (
    <Box
      bg="bg.muted/60"
      p={5}
      borderRadius="xl"
      borderWidth="1px"
      borderColor="border.subtle"
      height="fit-content"
    >
      <Flex align="center" justify="space-between" mb={2}>
        <Flex align="center" gap={2}>
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
        {items.length > 1 && (
          <Text
            fontSize="2xs"
            fontWeight="semibold"
            color="teal.fg"
            cursor="pointer"
            onClick={toggleAll}
            _hover={{ textDecoration: "underline", color: "teal.fg/80" }}
            userSelect="none"
          >
            {isAllExpanded ? "Collapse All" : "Expand All"}
          </Text>
        )}
      </Flex>
      <Text fontSize="xs" color="fg.muted" mb={4}>
        {subtitle}
      </Text>

      <VStack gap={2} align="stretch">
        {items.map((item) => (
          <FieldGuideCard
            key={item.label}
            item={item}
            isOpen={!!expandedLabels[item.label]}
            onToggle={() => toggleItem(item.label)}
          />
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
