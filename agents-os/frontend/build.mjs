import * as esbuild from "esbuild";

const isWatch = process.argv.includes("--watch");

const ctx = await esbuild.context({
  entryPoints: ["src/main.ts"],
  bundle: true,
  minify: !isWatch,
  sourcemap: true,
  target: ["es2022"],
  format: "iife",
  outfile: "dist/app.js",
  globalName: "AgentOS",
  loader: { ".ts": "ts" },
  logLevel: "info",
});

if (isWatch) {
  await ctx.watch();
  console.log("Watching for changes...");
} else {
  await ctx.rebuild();
  await ctx.dispose();
  console.log("Build complete → dist/app.js");
}
