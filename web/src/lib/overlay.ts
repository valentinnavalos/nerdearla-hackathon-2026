import type { Lang } from "@/types/session"

export type OverlayBg = "transparent" | "green"
export type OverlaySize = "M" | "L"

export interface OverlayParams {
  bg: OverlayBg
  size: OverlaySize
  lines: number
  lang: Lang
}

export const DEFAULT_OVERLAY_PARAMS: OverlayParams = {
  bg: "transparent",
  size: "M",
  lines: 3,
  lang: "es",
}

// Mirrors the query params OverlayPage.tsx reads (bg/size/lines/lang), so the
// generated URL matches exactly what the OBS/vMix Browser Source will render.
export function buildOverlayUrl(id: string, params: OverlayParams): string {
  const search = new URLSearchParams({
    bg: params.bg,
    size: params.size,
    lines: String(params.lines),
    lang: params.lang,
  })
  return `${location.origin}/overlay/${encodeURIComponent(id)}?${search.toString()}`
}
