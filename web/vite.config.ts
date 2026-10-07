import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Built assets go into the Python package so `auctionsi serve` can host them.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/",
  build: {
    outDir: "../src/auctionsi/api/static",
    emptyOutDir: true,
  },
  server: {
    port: 5180,
    proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true } },
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
