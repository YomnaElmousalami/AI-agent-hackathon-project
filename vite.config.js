import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '127.0.0.1',
    strictPort: true,
    proxy: {
      '/api': {
        // Backend FastAPI server (see api_server.py / uvicorn).
        target: 'http://127.0.0.1:8801',
        changeOrigin: true,
        secure: false,
      },
    },
  }
});
