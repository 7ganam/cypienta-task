import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import react from "@vitejs/plugin-react";
import { nitro } from "nitro/vite";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  if (!process.env.BACKEND_URL && env.BACKEND_URL)
    process.env.BACKEND_URL = env.BACKEND_URL;
  return {
    server: { port: 3000, strictPort: true },
    plugins: [tanstackStart(), nitro({ preset: "node-server" }), react()],
  };
});
