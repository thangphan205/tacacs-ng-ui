import { createFileRoute } from "@tanstack/react-router"
import { TacacsStatistics } from "./tacacs_statistics"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
})

function Dashboard() {
  return (
    <TacacsStatistics />
  )
}
