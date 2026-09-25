import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface AdminLoginGateProps {
  onSubmit: (token: string) => void
  error: string | null
}

export function AdminLoginGate({ onSubmit, error }: AdminLoginGateProps) {
  const [token, setToken] = useState("")

  return (
    <div className="mx-auto max-w-sm space-y-3 pt-16">
      <Label htmlFor="token">Admin token</Label>
      <Input
        id="token"
        autoComplete="off"
        placeholder="ADMIN_TOKEN"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && token && onSubmit(token)}
      />
      <Button type="button" className="w-full" onClick={() => token && onSubmit(token)}>
        Entrar
      </Button>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
