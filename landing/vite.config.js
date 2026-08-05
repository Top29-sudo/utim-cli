import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'https://api.utim.dev',
        changeOrigin: true,
        secure: false
      }
    }
  },
  build: {
    // Raise the advisory limit – we chunk explicitly below, so warnings above
    // 700 kB are legitimate and should not be silenced entirely.
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // ── Firebase (auth, firestore, app) ──────────────────────────────
          if (id.includes('node_modules/firebase') ||
              id.includes('node_modules/@firebase')) {
            return 'vendor-firebase'
          }
          // ── Three.js + React-Three ecosystem ────────────────────────────
          if (id.includes('node_modules/three') ||
              id.includes('node_modules/@react-three')) {
            return 'vendor-three'
          }
          // ── Framer Motion ────────────────────────────────────────────────
          if (id.includes('node_modules/framer-motion')) {
            return 'vendor-framer-motion'
          }
          // ── React core + React-DOM + React-Router ────────────────────────
          if (id.includes('node_modules/react') ||
              id.includes('node_modules/react-dom') ||
              id.includes('node_modules/react-router-dom') ||
              id.includes('node_modules/scheduler')) {
            return 'vendor-react'
          }
          // ── Markdown rendering ───────────────────────────────────────────
          if (id.includes('node_modules/react-markdown') ||
              id.includes('node_modules/remark') ||
              id.includes('node_modules/rehype') ||
              id.includes('node_modules/unified') ||
              id.includes('node_modules/micromark') ||
              id.includes('node_modules/mdast') ||
              id.includes('node_modules/hast')) {
            return 'vendor-markdown'
          }
          // ── Everything else in node_modules ─────────────────────────────
          if (id.includes('node_modules')) {
            return 'vendor-misc'
          }
        }
      }
    }
  }
})