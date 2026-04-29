import http from "node:http";
import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const args = new Map(process.argv.slice(2).map((arg) => {
  const [key, value] = arg.replace(/^--/, "").split("=");
  return [key, value || true];
}));
const host = args.get("host") || "0.0.0.0";
const port = Number(args.get("port") || 8013);
const clients = new Set();
let currentState = {
  index: 0,
  total: 0,
  file: "",
  title: "",
  speaker: "",
  notes: "",
};

const types = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".yaml": "text/yaml; charset=utf-8",
  ".yml": "text/yaml; charset=utf-8",
};

function sendState(response) {
  response.write(`data: ${JSON.stringify(currentState)}\n\n`);
}

function broadcastState() {
  for (const client of clients) {
    sendState(client);
  }
}

function serveFile(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);
  const requestedPath = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
  const filePath = normalize(join(root, requestedPath));

  if (!filePath.startsWith(root) || !existsSync(filePath) || !statSync(filePath).isFile()) {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found");
    return;
  }

  response.writeHead(200, { "Content-Type": types[extname(filePath)] || "application/octet-stream" });
  createReadStream(filePath).pipe(response);
}

const server = http.createServer((request, response) => {
  if (request.url === "/speaker/events") {
    response.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "Access-Control-Allow-Origin": "*",
    });
    clients.add(response);
    sendState(response);
    request.on("close", () => clients.delete(response));
    return;
  }

  if (request.url === "/speaker/state" && request.method === "POST") {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => {
      try {
        currentState = JSON.parse(body);
        broadcastState();
        response.writeHead(204);
      } catch {
        response.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
        response.end("Invalid slide state");
      }
      response.end();
    });
    return;
  }

  serveFile(request, response);
});

server.listen(port, host, () => {
  console.log(`Presentation: http://${host === "0.0.0.0" ? "localhost" : host}:${port}/`);
  console.log(`Speaker notes: http://${host === "0.0.0.0" ? "localhost" : host}:${port}/speaker-notes.html`);
});
