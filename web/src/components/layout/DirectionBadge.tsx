import { Lock } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { LANG_SHORT } from "@/lib/constants"
import type { Lang } from "@/types/session"

interface DirectionBadgeProps {
  sourceLang: Lang
  targetLang: Lang
}

// The translation direction is fixed for the whole session (the backend never
// re-derives target_lang once the Session is created): read-only, unlike the
// interactive language toggle.
export function DirectionBadge({ sourceLang, targetLang }: DirectionBadgeProps) {
  return (
    <Badge variant="outline" title="Dirección fija de la sesión: no se puede cambiar" className="gap-1">
      {LANG_SHORT[sourceLang]} → {LANG_SHORT[targetLang]}
      <Lock className="size-3" />
    </Badge>
  )
}
