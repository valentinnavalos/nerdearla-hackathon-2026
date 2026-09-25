import { Download } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { getExportUrl } from "@/lib/api"
import type { ExportFormat, Lang, SessionStatus } from "@/types/session"

interface ExportMenuProps {
  id: string
  status: SessionStatus
}

export function ExportMenu({ id, status }: ExportMenuProps) {
  const [fmt, setFmt] = useState<ExportFormat>("srt")
  const [lang, setLang] = useState<Lang>("es")
  const partial = status !== "STOPPED"

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button type="button" size="sm" variant="outline">
          <Download className="size-3.5" />
          Exportar
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 space-y-3">
        {partial && (
          <p className="text-xs text-muted-foreground">
            La sala sigue en vivo: se exporta lo transcripto hasta ahora.
          </p>
        )}
        <div className="flex items-center gap-2">
          <Select value={fmt} onValueChange={(v) => setFmt(v as ExportFormat)}>
            <SelectTrigger size="sm" className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="srt">SRT</SelectItem>
              <SelectItem value="vtt">VTT</SelectItem>
              <SelectItem value="txt">TXT</SelectItem>
              <SelectItem value="md">MD (ambos)</SelectItem>
            </SelectContent>
          </Select>
          <Select value={lang} onValueChange={(v) => setLang(v as Lang)} disabled={fmt === "md"}>
            <SelectTrigger size="sm" className="w-16">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="es">ES</SelectItem>
              <SelectItem value="en">EN</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button
          type="button"
          size="sm"
          className="w-full"
          onClick={() => window.open(getExportUrl(id, fmt, lang), "_blank")}
        >
          Descargar
        </Button>
      </PopoverContent>
    </Popover>
  )
}
