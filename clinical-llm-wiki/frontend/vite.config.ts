import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    base: "./",
    server: {
      proxy: {
        "/api/prerelease/v1": {
          target: environment.VITE_KNOWLEDGE_API_TARGET ?? "http://127.0.0.1:8788",
          changeOrigin: false,
        },
      },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
      rollupOptions: {
        input: resolve(__dirname, "app.html"),
      },
    },
    test: {
      environment: "jsdom",
      environmentOptions: {
        jsdom: {
          url: "http://127.0.0.1:4173/app.html",
        },
      },
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: true,
    },
  };
});
