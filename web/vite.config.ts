import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  // dev only: the API runs separately on 8000. In production FastAPI serves
  // this app's build output, so there is no proxy and no second origin.
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
})
