import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createRootRoute,
  HeadContent,
  Outlet,
  Scripts,
} from "@tanstack/react-router";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/dm-sans/700.css";
import stylesheet from "../styles.css?url";

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Usage overview · Cypienta" },
      {
        name: "description",
        content:
          "Your usage, at a glance. Explore activity and simulate usage in your Cypienta workspace.",
      },
    ],
    links: [
      { rel: "stylesheet", href: stylesheet },
      { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" },
    ],
  }),
  component: Root,
  notFoundComponent: () => (
    <main className="not-found">
      <h1>Page not found</h1>
      <a href="/">Back to your dashboard</a>
    </main>
  ),
  errorComponent: ({ reset }) => (
    <main className="not-found">
      <h1>Something went wrong</h1>
      <button onClick={reset}>Try again</button>
    </main>
  ),
});

function Root() {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: true },
          mutations: { retry: false },
        },
      }),
  );
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        <QueryClientProvider client={client}>
          <Outlet />
        </QueryClientProvider>
        <Scripts />
      </body>
    </html>
  );
}
