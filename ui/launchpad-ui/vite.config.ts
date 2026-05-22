import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/launchpad/",
  server: {
    port: 3100,
    proxy: {
      "/api/tech": {
        target: "http://127.0.0.1:8104",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/tech/, "/api/v1"),
      },
    },
  },
});
