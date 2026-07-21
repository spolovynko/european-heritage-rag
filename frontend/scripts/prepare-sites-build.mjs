import { cp, mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectDirectory = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const distributionDirectory = resolve(projectDirectory, "dist");
const clientDirectory = resolve(distributionDirectory, "client");
const serverDirectory = resolve(distributionDirectory, "server");

await mkdir(clientDirectory, { recursive: true });
await mkdir(serverDirectory, { recursive: true });
await cp(resolve(distributionDirectory, "index.html"), resolve(clientDirectory, "index.html"));
await cp(resolve(distributionDirectory, "assets"), resolve(clientDirectory, "assets"), {
  recursive: true
});

const workerSource = `export default {
  async fetch(request, env) {
    if (!env.ASSETS) {
      return new Response("Static asset binding unavailable", { status: 503 });
    }

    const response = await env.ASSETS.fetch(request);
    if (response.status !== 404 || request.method !== "GET") {
      return response;
    }

    const fallbackUrl = new URL(request.url);
    fallbackUrl.pathname = "/index.html";
    return env.ASSETS.fetch(new Request(fallbackUrl, request));
  }
};
`;

await writeFile(resolve(serverDirectory, "index.js"), workerSource, "utf8");
