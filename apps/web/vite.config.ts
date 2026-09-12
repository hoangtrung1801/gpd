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
      "/api": {
        target: `http://${process.env.GPD_API_HOST || "100.67.176.76"}:${process.env.GPD_API_PORT || "4040"}`,
        changeOrigin: true,
        headers: {
          Authorization: `Bearer ${process.env.GPD_ACCESS_TOKEN || "dev-local-token"}`,
        },
      },
      "/health": {
        target: `http://${process.env.GPD_API_HOST || "100.67.176.76"}:${process.env.GPD_API_PORT || "4040"}`,
        changeOrigin: true,
        headers: {
          Authorization: `Bearer ${process.env.GPD_ACCESS_TOKEN || "dev-local-token"}`,
        },
      },
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
