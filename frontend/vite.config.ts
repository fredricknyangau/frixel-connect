import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      // By proxying /api to the backend during development, 
      // the frontend and backend appear to run on the same origin (localhost:5173).
      // This avoids CORS (Cross-Origin Resource Sharing) issues during local development,
      // which is exactly like using Nginx as a reverse proxy in production to route
      // /api traffic to your FastAPI backend and / traffic to your React static files.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
