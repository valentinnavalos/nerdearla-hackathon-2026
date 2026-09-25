import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { PilusoLogo } from "@/components/brand/PilusoLogo"

interface PageShellProps {
  children: ReactNode
  title?: string
}

export function PageShell({ children, title }: PageShellProps) {
  return (
    <div className="mx-auto max-w-3xl px-4 pb-16 pt-8">
      <header className="mb-6 flex items-center justify-between">
        <Link to="/" className="rounded-md text-foreground hover:opacity-80 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none">
          <PilusoLogo showPartner />
        </Link>
        {title ? <span className="text-sm text-muted-foreground">{title}</span> : null}
      </header>
      {children}
    </div>
  )
}
