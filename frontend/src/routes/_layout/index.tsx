import { createFileRoute } from "@tanstack/react-router"
import { AaaStatisticsRange } from "./aaa_statistics_range"
import { AaaStatistics } from "./aaa_statistics"
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
