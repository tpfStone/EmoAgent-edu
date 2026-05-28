import { spawnSync } from "node:child_process";
import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workspaceRoot = path.resolve(__dirname, "..");
const siteRoot = path.join(workspaceRoot, "dist-pages");
const pnpm = process.platform === "win32" ? "pnpm.cmd" : "pnpm";

function runBuild(packageName) {
  const result = spawnSync(
    pnpm,
    ["--filter", packageName, "build"],
    {
      cwd: workspaceRoot,
      env: {
        ...process.env,
        VITE_API_MODE: "mock",
        VITE_API_BASE: "",
        VITE_BASE_PATH: "./",
      },
      stdio: "inherit",
      shell: process.platform === "win32",
    },
  );

  if (result.error) {
    throw result.error;
  }

  if (result.status !== 0) {
    throw new Error(`${packageName} pages build failed with exit ${result.status}`);
  }
}

async function copyApp(appName) {
  await cp(path.join(workspaceRoot, appName, "dist"), path.join(siteRoot, appName), {
    recursive: true,
  });
}

await rm(siteRoot, { force: true, recursive: true });
await mkdir(siteRoot, { recursive: true });

runBuild("@emoedu/student");
runBuild("@emoedu/console");

await copyApp("student");
await copyApp("console");
await writeFile(path.join(siteRoot, ".nojekyll"), "");
await writeFile(
  path.join(siteRoot, "index.html"),
  `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>EmoAgent Demo</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #faf8f3;
        color: #33312c;
        font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
      }

      main {
        display: grid;
        gap: 16px;
        width: min(520px, calc(100vw - 32px));
      }

      h1,
      p {
        margin: 0;
      }

      h1 {
        font-size: 28px;
        line-height: 1.2;
      }

      p {
        color: #6f6a61;
        line-height: 1.7;
      }

      nav {
        display: grid;
        gap: 10px;
      }

      a {
        display: block;
        padding: 14px 16px;
        border: 1px solid #d8cfbd;
        border-radius: 8px;
        background: #fffefb;
        color: inherit;
        font-weight: 700;
        text-decoration: none;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>EmoAgent Demo</h1>
      <p>这是 GitHub Pages mock 演示版。真实 /chat 联调请使用本机 live 演示。</p>
      <nav aria-label="Demo apps">
        <a href="./student/">学生端</a>
        <a href="./console/">研究分析台</a>
      </nav>
    </main>
  </body>
</html>
`,
);
