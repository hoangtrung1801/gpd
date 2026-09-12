import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "node:crypto": path.resolve(__dirname, "./src/polyfills/crypto.ts"),
      crypto: path.resolve(__dirname, "./src/polyfills/crypto.ts"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": "http://127.0.0.1:7337",
      "/health": "http://127.0.0.1:7337",
    },
  },
  // @ts-expect-error vitest extends vite config with test field
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
  },
});
