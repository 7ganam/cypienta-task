import { createFileRoute } from "@tanstack/react-router";
import { proxyRequest } from "../server/usage-backend";

export const Route = createFileRoute("/api/$")({
  server: {
    handlers: {
      GET: ({ request }) => proxyRequest(request),
      POST: ({ request }) => proxyRequest(request),
    },
  },
});
