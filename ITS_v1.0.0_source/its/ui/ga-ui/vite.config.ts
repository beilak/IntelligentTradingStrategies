import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "/ga/",
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
    port: 3103,
    proxy: {
      "/api/ga": {
        target: "http://127.0.0.1:8103",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/ga/, "/api/v1"),
      },
    },
  },
});

