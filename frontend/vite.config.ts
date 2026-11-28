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
    // CI also writes JUnit results for the build artifacts and job summary (see docs/ci.md).
    reporters: process.env.CI ? ['default', 'junit'] : ['default'],
    outputFile: { junit: './reports/junit.xml' },
    // `npm run test:coverage` enforces the 70% line threshold (US-00.4).
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/api/generated/**', 'src/**/*.d.ts'],
      reporter: ['text-summary', 'cobertura', 'html', 'json-summary'],
      reportsDirectory: './coverage',
      thresholds: { lines: 70 },
    },
  },
})
