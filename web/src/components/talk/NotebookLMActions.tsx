import { Copy, ExternalLink, Headphones } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { getExportUrl } from "@/lib/api"
import type { Lang } from "@/types/session"

const NOTEBOOKLM_URL = "https://notebooklm.google.com"

const LABELS = {
  es: {
    copy: "Copiar para NotebookLM",
    copied: "Copiado: pegalo en NotebookLM como fuente (\"Texto copiado\").",
    downloaded: "No se pudo copiar: se descargó el .md, subilo a NotebookLM como fuente.",
    failed: "No se pudo obtener la transcripción.",
    podcast: "Abrir notebook con podcast",
  },
  en: {
    copy: "Copy for NotebookLM",
    copied: "Copied: paste it into NotebookLM as a source (\"Copied text\").",
    downloaded: "Could not copy: the .md was downloaded, upload it to NotebookLM as a source.",
    failed: "Could not fetch the transcript.",
    podcast: "Open notebook with podcast",
  },
}

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }))
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

interface NotebookLMActionsProps {
  sessionId: string
  lang: Lang
  notebookUrl: string | null
  /** Bump it (e.g. with kp_status) to re-fetch the MD once the Knowledge Pack lands in it. */
  version: string
}

async function fetchMd(sessionId: string): Promise<string> {
  const res = await fetch(getExportUrl(sessionId, "md"))
  if (!res.ok) throw new Error(String(res.status))
  return res.text()
}

/** Capa 3 (always there) + capa 2's link when the automatic exporter ran (PLAN.md §3). */
export function NotebookLMActions({ sessionId, lang, notebookUrl, version }: NotebookLMActionsProps) {
  const t = LABELS[lang]
  const [md, setMd] = useState<string | null>(null)

  // prefetched, so the click can write to the clipboard while the page still has focus
  useEffect(() => {
    let cancelled = false
    fetchMd(sessionId)
      .then((text) => !cancelled && setMd(text))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [sessionId, version])

  async function copyForNotebookLM() {
    let text = md
    try {
      text ??= await fetchMd(sessionId)
    } catch {
      toast.error(t.failed)
      return
    }
    try {
      await navigator.clipboard.writeText(text)
      toast.success(t.copied)
    } catch {
      download(`${sessionId}.md`, text)
      toast.info(t.downloaded)
    }
    window.open(NOTEBOOKLM_URL, "_blank", "noopener")
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button onClick={copyForNotebookLM}>
        <Copy className="size-4" />
        {t.copy}
        <ExternalLink className="size-3.5 opacity-70" />
      </Button>
      {notebookUrl && (
        <Button variant="secondary" asChild>
          <a href={notebookUrl} target="_blank" rel="noreferrer">
            <Headphones className="size-4" />
            {t.podcast}
          </a>
        </Button>
      )}
    </div>
  )
}
