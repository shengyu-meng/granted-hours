import { createReadStream, existsSync, statSync } from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";

const rootDir = process.cwd();
const docsDir = path.join(rootDir, "docs");
const docsPrefix = `${docsDir}${path.sep}`;

function docsDevAssets() {
  return {
    name: "docs-dev-assets",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        let url;
        try {
          url = decodeURIComponent((req.url || "").split("?")[0]);
        } catch {
          next();
          return;
        }
        if (!url.startsWith("/archive/") && !url.startsWith("/maze/") && !url.startsWith("/inaugural/")) {
          next();
          return;
        }
        const filePath = path.resolve(docsDir, `.${url}`);
        if (!filePath.startsWith(docsPrefix)) {
          next();
          return;
        }
        const candidate = existsSync(filePath) && statSync(filePath).isDirectory()
          ? path.join(filePath, "index.html")
          : filePath;
        if (!existsSync(candidate) || !statSync(candidate).isFile()) {
          next();
          return;
        }
        const ext = path.extname(candidate);
        const type = {
          ".css": "text/css",
          ".gif": "image/gif",
          ".html": "text/html",
          ".js": "text/javascript",
          ".mp3": "audio/mpeg",
          ".png": "image/png",
        }[ext] || "application/octet-stream";
        res.setHeader("Content-Type", `${type}; charset=utf-8`);
        createReadStream(candidate).pipe(res);
      });
    },
  };
}

export default defineConfig({
  root: "src/timetable",
  base: "./",
  plugins: [docsDevAssets()],
  publicDir: false,
  build: {
    outDir: "../../docs/timetable",
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
