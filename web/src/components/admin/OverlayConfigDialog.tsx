import { Check, Copy } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { buildOverlayUrl, DEFAULT_OVERLAY_PARAMS, type OverlayBg, type OverlaySize } from "@/lib/overlay"
import type { Lang } from "@/types/session"

interface OverlayConfigDialogProps {
  id: string
}

export function OverlayConfigDialog({ id }: OverlayConfigDialogProps) {
  const [params, setParams] = useState(DEFAULT_OVERLAY_PARAMS)
  const [copied, setCopied] = useState(false)
  const url = buildOverlayUrl(id, params)

  async function copyUrl() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      toast.success("URL copiada")
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error("No se pudo copiar la URL")
    }
  }

  return (
    <Dialog onOpenChange={(open) => !open && setCopied(false)}>
      <DialogTrigger asChild>
        <Button type="button" size="sm" variant="outline">
          Overlay
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Overlay para OBS/vMix</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Fondo</Label>
              <Select
                value={params.bg}
                onValueChange={(v) => setParams((p) => ({ ...p, bg: v as OverlayBg }))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="transparent">Transparente</SelectItem>
                  <SelectItem value="green">Chroma verde</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Tamaño</Label>
              <Select
                value={params.size}
                onValueChange={(v) => setParams((p) => ({ ...p, size: v as OverlaySize }))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="M">Mediano</SelectItem>
                  <SelectItem value="L">Grande</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Líneas visibles</Label>
              <Input
                type="number"
                min={1}
                max={10}
                value={params.lines}
                onChange={(e) =>
                  setParams((p) => ({ ...p, lines: Math.max(1, Number(e.target.value) || 1) }))
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label>Idioma</Label>
              <Select value={params.lang} onValueChange={(v) => setParams((p) => ({ ...p, lang: v as Lang }))}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="es">Español</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>URL para el Browser Source</Label>
            <Input readOnly value={url} onFocus={(e) => e.target.select()} className="font-mono text-xs" />
          </div>
        </div>
        <DialogFooter className="gap-2 sm:justify-between">
          <Button type="button" variant="outline" onClick={copyUrl}>
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            Copiar
          </Button>
          <Button type="button" asChild>
            <a href={url} target="_blank" rel="noreferrer">
              Abrir
            </a>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
