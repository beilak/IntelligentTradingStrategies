import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/tech/",
  server: {
    port: 3104,
    proxy: {
      "/api/tech": {
        target: "http://127.0.0.1:8104",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/tech/, "/api/v1"),
      },
      "/api/event-log": {
        target: "http://127.0.0.1:8105",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/event-log/, "/api/v1"),
      },
    },
  },
});
