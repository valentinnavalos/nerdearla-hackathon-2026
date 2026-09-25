import { Navigate, useSearchParams } from "react-router-dom"
import { RoomListPage } from "./RoomListPage"

// Backwards-compat for OBS scenes already configured with the old query-string
// URL shape (index.html?s=<id>&overlay=1&...). New rooms use /overlay/:id and
// /watch/:id instead, but old saved Browser Source URLs must keep working.
export function RootRoute() {
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get("s")

  if (sessionId) {
    const rest = new URLSearchParams(searchParams)
    rest.delete("s")
    rest.delete("overlay")
    const query = rest.toString()
    const path = searchParams.get("overlay") === "1" ? `/overlay/${sessionId}` : `/watch/${sessionId}`
    return <Navigate to={query ? `${path}?${query}` : path} replace />
  }

  return <RoomListPage />
}
