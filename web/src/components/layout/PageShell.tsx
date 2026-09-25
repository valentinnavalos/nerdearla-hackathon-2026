import type { ReactNode } from "react"
import { Link } from "react-router-dom"

interface PageShellProps {
  children: ReactNode
  title?: string
}

export function PageShell({ children, title }: PageShellProps) {
  return (
    <div className="mx-auto max-w-3xl px-4 pb-16 pt-8">
      <header className="mb-6 flex items-center justify-between">
        <Link to="/" className="text-sm font-semibold tracking-tight text-foreground hover:text-primary">
          Nerdearla Live Captions
        </Link>
        {title ? <span className="text-sm text-muted-foreground">{title}</span> : null}
      </header>
      {children}
    </div>
  )
}
