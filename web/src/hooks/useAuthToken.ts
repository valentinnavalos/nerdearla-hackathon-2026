import { useCallback, useState } from "react"

const TOKEN_KEY = "admin.token"

// sessionStorage, not localStorage: the admin token must not survive the tab closing.
function readStoredToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? ""
  } catch {
    return ""
  }
}

function writeStoredToken(token: string) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
  } catch {
    /* ignore: private mode / blocked storage */
  }
}

export function useAuthToken() {
  const [token, setTokenState] = useState<string>(() => readStoredToken())

  const setToken = useCallback((next: string) => {
    writeStoredToken(next)
    setTokenState(next)
  }, [])

  return { token, setToken }
}
