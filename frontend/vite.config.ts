import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// En desarrollo, /api va al backend local. En producción lo resuelve nginx (mismo origen).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  preview: { proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { chunkSizeWarningLimit: 1500 },
});
