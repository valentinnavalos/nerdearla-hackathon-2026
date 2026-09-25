import { BrowserRouter, Route, Routes } from "react-router-dom"
import { Toaster } from "@/components/ui/sonner"
import { AdminPage } from "@/pages/AdminPage"
import { AudienceViewPage } from "@/pages/AudienceViewPage"
import { OverlayPage } from "@/pages/OverlayPage"
import { RootRoute } from "@/pages/RootRoute"
import { StagePage } from "@/pages/StagePage"
import { TalkPage } from "@/pages/TalkPage"

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RootRoute />} />
        <Route path="/watch/:sessionId" element={<AudienceViewPage />} />
        <Route path="/overlay/:sessionId" element={<OverlayPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/stage/:sessionId" element={<StagePage />} />
        <Route path="/talk/:sessionId" element={<TalkPage />} />
      </Routes>
      <Toaster richColors position="top-right" />
    </BrowserRouter>
  )
}

export default App
