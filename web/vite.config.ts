import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the Flask server runs on :5078 (see README); in production Flask
// serves the built app itself, so the API is always same-origin.
const api = process.env.BOREDROOM_API ?? 'http://127.0.0.1:5078'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': api, '/privacy': api, '/terms': api, '/health': api },
  },
})
