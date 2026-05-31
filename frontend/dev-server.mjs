import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL(".", import.meta.url)));
const port = Number(process.env.PORT || 5173);

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
};

function resolveRequestPath(url) {
  const pathname = decodeURIComponent(new URL(url, `http://127.0.0.1:${port}`).pathname);
  const normalizedPath = normalize(pathname).replace(/^(\.\.[/\\])+/, "");
  const publicRoot = join(root, "public");
  const publicCandidate = resolve(join(publicRoot, normalizedPath));

  if (publicCandidate.startsWith(publicRoot) && existsSync(publicCandidate) && statSync(publicCandidate).isFile()) {
    return publicCandidate;
  }

  const candidate = resolve(join(root, normalizedPath));

  if (!candidate.startsWith(root)) {
    return null;
  }

  if (existsSync(candidate) && statSync(candidate).isFile()) {
    return candidate;
  }

  return join(root, "index.html");
}

createServer((request, response) => {
  const filePath = resolveRequestPath(request.url || "/");

  if (!filePath) {
    response.writeHead(403);
    response.end("Forbidden");
    return;
  }

  const contentType = mimeTypes[extname(filePath)] || "application/octet-stream";
  response.writeHead(200, {
    "Content-Type": contentType,
    "Cache-Control": "no-store",
  });
  createReadStream(filePath).pipe(response);
}).listen(port, "127.0.0.1", () => {
  console.log(`FilmRevive frontend ready at http://127.0.0.1:${port}`);
});
