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
      "/api": "http://100.67.176.76:4040",
      "/health": "http://100.67.176.76:4040",
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
