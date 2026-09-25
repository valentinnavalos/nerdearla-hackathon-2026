export const BRAND_NAME = "Piluso"
export const PRODUCT_NAME = "Piluso Live Captions"

// Endorsement shown next to the logo ("para Nerdearla"). Set at build time;
// an empty VITE_PARTNER_NAME hides it. The default lives here (and in the
// Dockerfile ARG) because web/.env is gitignored and never reaches CI builds.
export const PARTNER_NAME = (import.meta.env.VITE_PARTNER_NAME ?? "Nerdearla").trim()
