import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// File watching via polling is slower but reliable on Docker bind mounts (notably on Windows).
const usePolling = process.env.DEV_WATCH_POLLING === 'true'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
  },
})
