import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // Tailwind v4 is a Vite plugin, not a PostCSS config file + separate CLI
  // step — this one line plus the single @import in index.css is the whole
  // setup. There is no tailwind.config.js; v4 scans source files for class
  // names automatically instead of needing a `content` glob declared.
  plugins: [react(), tailwindcss()],
})
