import { useCallback, useMemo, useReducer } from "react"
import { wsUrl } from "@/lib/ws"
import type { CaptionSegment, CaptionSocketMessage } from "@/types/caption"
import type { Lang, SessionStatus } from "@/types/session"
import { useReconnectingSocket } from "./useReconnectingSocket"

const MAX_SEGS = 50

interface CaptionState {
  segsBySeg: Map<number, CaptionSegment>
  status: SessionStatus | null
}

type CaptionAction =
  | { type: "RESET" }
  | { type: "STATUS_CHANGED"; status: SessionStatus }
  | { type: "CAPTION"; seg: number; text: string; final: boolean }

function reducer(state: CaptionState, action: CaptionAction): CaptionState {
  switch (action.type) {
    case "RESET":
      return { segsBySeg: new Map(), status: state.status }
    case "STATUS_CHANGED": {
      // a restarted room starts segment ids over
      const restarted = state.status !== null && state.status !== "RUNNING" && action.status === "RUNNING"
      return { segsBySeg: restarted ? new Map() : state.segsBySeg, status: action.status }
    }
    case "CAPTION": {
      const current = state.segsBySeg.get(action.seg)
      if (current?.final && !action.final) return state // late interim after its final
      const next = new Map(state.segsBySeg)
      next.set(action.seg, { seg: action.seg, text: action.text, final: action.final })
      if (next.size > MAX_SEGS) {
        const oldest = [...next.keys()].sort((a, b) => a - b).slice(0, next.size - MAX_SEGS)
        for (const seg of oldest) next.delete(seg)
      }
      return { ...state, segsBySeg: next }
    }
    default:
      return state
  }
}

export function useCaptionSocket(sessionId: string | null, lang: Lang) {
  const [state, dispatch] = useReducer(reducer, { segsBySeg: new Map(), status: null })

  const url = sessionId
    ? wsUrl(`/ws/captions/${encodeURIComponent(sessionId)}?lang=${encodeURIComponent(lang)}`)
    : null

  const onMessage = useCallback((ev: MessageEvent) => {
    const msg = JSON.parse(ev.data) as CaptionSocketMessage
    if (msg.type === "session_status") {
      dispatch({ type: "STATUS_CHANGED", status: msg.status })
    } else if (msg.type === "caption") {
      dispatch({ type: "CAPTION", seg: msg.seg, text: msg.text, final: msg.final })
    }
  }, [])

  const onOpen = useCallback(() => {
    // the server resends the full history of finals on every (re)connect
    dispatch({ type: "RESET" })
  }, [])

  const { connectionState, lastCloseCode } = useReconnectingSocket({ url, onMessage, onOpen })

  const segments = useMemo(
    () => [...state.segsBySeg.values()].sort((a, b) => a.seg - b.seg),
    [state.segsBySeg],
  )

  return { segments, status: state.status, connectionState, lastCloseCode }
}
