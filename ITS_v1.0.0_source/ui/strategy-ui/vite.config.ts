import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "/strategies/",
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/vue")) return "vue";
          if (id.includes("node_modules/lucide-vue-next")) return "icons";
        },
      },
    },
  },
  server: {
    port: 3102,
    proxy: {
      "/api/strategies": {
        target: "http://127.0.0.1:8102",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/strategies/, "/api/v1"),
      },
    },
  },
});
