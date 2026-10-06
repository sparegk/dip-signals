import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { readFile } from 'node:fs/promises'
import { resolve, sep } from 'node:path'

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'research-export-files',
      configureServer(server) {
        // Vite caches public paths through its watcher. Serve generated JSON
        // directly so new generations are available without Windows watch locks.
        const dataRoot = resolve(server.config.publicDir, 'data')
        server.middlewares.use((request, response, next) => {
          const pathname = (request.url ?? '').split('?')[0]
          if (!pathname.startsWith('/data/')) return next()
          const relative = pathname.slice('/data/'.length)
          const target = resolve(dataRoot, relative)
          if (!/^[\w/.-]+\.json$/.test(relative) || !target.startsWith(dataRoot + sep)) {
            response.statusCode = 400
            response.end('Invalid research export path')
            return
          }
          readFile(target)
            .then((bytes) => {
              response.setHeader('Content-Type', 'application/json; charset=utf-8')
              response.setHeader('Cache-Control', 'no-store')
              response.end(bytes)
            })
            .catch((error) => {
              response.statusCode = error.code === 'ENOENT' ? 404 : 500
              response.end('Research export unavailable')
            })
        })
      },
    },
  ],
  // Export generations are immutable and refreshed explicitly in the browser.
  // Avoid holding Windows file-watch handles on the atomically replaced manifest.
  server: { watch: { ignored: ['**/public/data/**'] } },
  base: './',
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: 'react', test: /node_modules[\\/]react(?:-dom)?[\\/]/, priority: 20 },
            {
              name: 'charts',
              test: /node_modules[\\/](?:recharts|d3-|victory|@reduxjs|react-redux|immer|reselect)/,
              priority: 10,
            },
          ],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
