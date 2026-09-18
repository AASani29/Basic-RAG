// tsconfig.app.json's "types": ["vite/client"] already supplies Vite's own
// ambient types (import.meta.env.MODE, .DEV, .PROD, etc.) — this file only
// adds the one env var this app actually defines, so accessing it gets
// autocomplete and a compile error on a typo instead of `any`.
interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
