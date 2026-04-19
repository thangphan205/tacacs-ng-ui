import { createFileRoute } from "@tanstack/react-router"
import { AaaStatistics } from "./aaa_statistics"
import { AaaStatisticsRange } from "./aaa_statistics_range"
export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
})

function Dashboard() {
  return (
    <>
      <AaaStatistics />
      <AaaStatisticsRange />
    </>
  )
}
