import { cpSync, existsSync } from "node:fs";

const standaloneRoot = new URL("../.next/standalone/", import.meta.url);

// Next's standalone output omits static/public files; mirror the Docker image.
cpSync(
  new URL("../.next/static/", import.meta.url),
  new URL(".next/static/", standaloneRoot),
  { recursive: true },
);
const publicRoot = new URL("../public/", import.meta.url);
if (existsSync(publicRoot)) {
  cpSync(publicRoot, new URL("public/", standaloneRoot), { recursive: true });
}

process.env.HOSTNAME = "127.0.0.1";
process.env.PORT = "3100";
await import(new URL("server.js", standaloneRoot));
