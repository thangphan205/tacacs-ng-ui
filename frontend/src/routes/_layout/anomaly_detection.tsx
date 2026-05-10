import {
  Badge,
  Box,
  Button,
  Container,
  EmptyState,
  Flex,
  Heading,
  Switch,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FiCpu, FiRefreshCw } from "react-icons/fi"
import { z } from "zod"

import { AnomalyDetectionService } from "@/client"
import { PageSizeSelect } from "@/components/Common/PageSizeSelect"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"

const DEFAULT_PER_PAGE = 20

const searchSchema = z.object({
  page: z.number().catch(1),
  anomaly_only: z.boolean().catch(false),
})

const RISK_COLORS: Record<string, string> = {
  normal: "gray",
  low: "blue",
  medium: "yellow",
  high: "orange",
  critical: "red",
}

interface QueryParams {
  page: number
  perPage: number
  anomalyOnly: boolean
}

function getQueryOptions({ page, perPage, anomalyOnly }: QueryParams) {
  return {
    queryFn: () =>
      AnomalyDetectionService.readAnomalyResults({
        skip: (page - 1) * perPage,
        limit: perPage,
        isAnomalyOnly: anomalyOnly,
        sortBy: "anomaly_score",
      }),
    queryKey: ["anomaly_detection", { page, perPage, anomalyOnly }],
  }
}

export const Route = createFileRoute("/_layout/anomaly_detection")({
  component: AnomalyDetectionPage,
  validateSearch: (search) => searchSchema.parse(search),
})

function RetrainButton() {
  const queryClient = useQueryClient()
  const [msg, setMsg] = useState<string | null>(null)
  const mutation = useMutation({
    mutationFn: () => AnomalyDetectionService.retrainAnomalyModel(),
    onSuccess: (data) => {
      setMsg(data.message as string)
      queryClient.invalidateQueries({ queryKey: ["anomaly_detection"] })
    },
    onError: () => setMsg("Retrain failed"),
  })

  return (
    <Flex align="center" gap={2}>
      <Button
        size="sm"
        variant="outline"
        loading={mutation.isPending}
        onClick={() => { setMsg(null); mutation.mutate() }}
      >
        <FiRefreshCw /> Retrain Model
      </Button>
      {msg && <Text fontSize="sm" color="fg.muted">{msg}</Text>}
    </Flex>
  )
}

function AnomalyTable() {
  const navigate = useNavigate({ from: Route.fullPath })
  const { page, anomaly_only } = Route.useSearch()
  const [perPage, setPerPage] = useState(DEFAULT_PER_PAGE)

  const { data, isLoading } = useQuery(
    getQueryOptions({ page, perPage, anomalyOnly: anomaly_only })
  )
  const count = data?.count ?? 0

  if (isLoading) return <Text>Loading...</Text>

  return (
    <Box>
      <Flex mb={4} gap={4} align="center">
        <PageSizeSelect value={perPage} onChange={(v) => { setPerPage(v); navigate({ search: (s) => ({ ...s, page: 1 }) }) }} />
        <Flex align="center" gap={2}>
          <Switch.Root
            checked={anomaly_only}
            onCheckedChange={(e) => navigate({ search: (s) => ({ ...s, anomaly_only: e.checked, page: 1 }) })}
          >
            <Switch.HiddenInput />
            <Switch.Control><Switch.Thumb /></Switch.Control>
          </Switch.Root>
          <Text fontSize="sm">Anomalies only</Text>
        </Flex>
      </Flex>

      {count === 0 ? (
        <EmptyState.Root>
          <EmptyState.Content>
            <VStack>
              <EmptyState.Indicator><FiCpu /></EmptyState.Indicator>
              <EmptyState.Title>No scoring data</EmptyState.Title>
              <EmptyState.Description>
                Run the model via "Retrain Model" or wait for the daily background scoring.
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      ) : (
        <>
          <Table.Root size="sm">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Subject Type</Table.ColumnHeader>
                <Table.ColumnHeader>Subject</Table.ColumnHeader>
                <Table.ColumnHeader>Risk Level</Table.ColumnHeader>
                <Table.ColumnHeader>Anomaly Score</Table.ColumnHeader>
                <Table.ColumnHeader>Anomaly</Table.ColumnHeader>
                <Table.ColumnHeader>Scored At</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {data?.data.map((r) => (
                <Table.Row key={r.id}>
                  <Table.Cell>
                    <Badge variant="outline">{r.subject_type}</Badge>
                  </Table.Cell>
                  <Table.Cell fontWeight="medium">{r.subject_value}</Table.Cell>
                  <Table.Cell>
                    <Badge colorPalette={RISK_COLORS[r.risk_level] ?? "gray"}>
                      {r.risk_level}
                    </Badge>
                  </Table.Cell>
                  <Table.Cell fontFamily="mono" fontSize="xs">
                    {r.anomaly_score.toFixed(4)}
                  </Table.Cell>
                  <Table.Cell>
                    {r.is_anomaly ? (
                      <Badge colorPalette="red">Yes</Badge>
                    ) : (
                      <Badge colorPalette="green">No</Badge>
                    )}
                  </Table.Cell>
                  <Table.Cell fontSize="xs" color="fg.muted" whiteSpace="nowrap">
                    {new Date(r.scored_at).toLocaleString()}
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table.Root>

          <PaginationRoot
            count={count}
            pageSize={perPage}
            page={page}
            onPageChange={(e) => navigate({ search: (s) => ({ ...s, page: e.page }) })}
          >
            <Flex mt={4} justify="center" gap={2}>
              <PaginationPrevTrigger />
              <PaginationItems />
              <PaginationNextTrigger />
            </Flex>
          </PaginationRoot>
        </>
      )}
    </Box>
  )
}

function AnomalyDetectionPage() {
  return (
    <Container maxW="full">
      <Flex pt={12} pb={4} justify="space-between" align="flex-start">
        <Box>
          <Heading size="lg">Anomaly Detection</Heading>
          <Text color="fg.muted" mt={1}>
            ML-based scoring of TACACS+ users using IsolationForest on 30-day rolling statistics.
            More negative score = more anomalous.
          </Text>
        </Box>
        <RetrainButton />
      </Flex>
      <AnomalyTable />
    </Container>
  )
}
