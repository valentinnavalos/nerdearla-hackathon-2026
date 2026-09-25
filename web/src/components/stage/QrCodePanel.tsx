import { QRCodeSVG } from "qrcode.react"

interface QrCodePanelProps {
  url: string
}

export function QrCodePanel({ url }: QrCodePanelProps) {
  return (
    <div className="absolute bottom-4 right-4 flex flex-col items-center gap-1 rounded-2xl bg-white p-2.5 shadow-lg">
      <QRCodeSVG value={url} size={120} />
      <span className="max-w-35 text-center text-[0.7rem] break-all text-neutral-900">{url}</span>
    </div>
  )
}
