import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // k8s dev-stand: requests come via ingress Host app.local (compose-era
    // dev used localhost). Empty default keeps localhost behavior; set
    // VITE_ALLOWED_HOSTS in the pod env to extend.
    allowedHosts: process.env.VITE_ALLOWED_HOSTS
      ? process.env.VITE_ALLOWED_HOSTS.split(',')
      : [],
    // k8s dev-stand (ADR-0030 §6): TLS terminates on the ingress, so the
    // browser-facing HMR websocket must be wss on 443. Set by values-dev.
    hmr: process.env.VITE_HMR_WSS === 'true'
      ? { protocol: 'wss', clientPort: Number(process.env.VITE_HMR_CLIENT_PORT) || 443 }
      : undefined,
    proxy: {
      '/api': {
        target: 'http://bigbug-backend:80',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  optimizeDeps: {
    include: ['@ant-design/x-markdown'],
  },
})
