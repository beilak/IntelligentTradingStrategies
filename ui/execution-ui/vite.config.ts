import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "/execution/",
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 650,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/echarts")) {
            return "echarts";
          }
          if (id.includes("node_modules/vue")) {
            return "vue";
          }
          if (id.includes("node_modules/lucide-vue-next")) {
            return "icons";
          }
        },
      },
    },
  },
  server: {
    port: 3104,
    proxy: {
      "/api/execution": {
        target: "http://127.0.0.1:8104",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/execution/, "/api/v1"),
      },
      "/api/data": {
        target: "http://127.0.0.1:8101",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/data/, "/api/v1"),
      },
      "/api/tech": {
        target: "http://127.0.0.1:8103",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/tech/, "/api/v1"),
      },
    },
  },
});
