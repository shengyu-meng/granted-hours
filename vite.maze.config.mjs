import { defineConfig } from "vite";

export default defineConfig({
  root: "src/maze",
  base: "./",
  build: {
    outDir: "../../docs/maze",
    emptyOutDir: true,
    assetsDir: "assets",
  },
  server: {
    host: "127.0.0.1",
  },
  preview: {
    host: "127.0.0.1",
  },
});
