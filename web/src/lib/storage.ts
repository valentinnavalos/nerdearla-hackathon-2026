// localStorage can throw (private mode, blocked storage): it only holds per-viewer conveniences.
export const storage = {
  get<T>(key: string, fallback: T): T {
    try {
      const value = localStorage.getItem(key)
      return value === null ? fallback : (JSON.parse(value) as T)
    } catch {
      return fallback
    }
  },
  set<T>(key: string, value: T): void {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {
      /* ignore */
    }
  },
}
