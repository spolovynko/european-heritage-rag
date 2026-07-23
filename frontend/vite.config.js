import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/ingestion": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/bronze": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/silver": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  }
});
