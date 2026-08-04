import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";

import "./app/theme.css";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { createAppRouter } from "./router";

async function enableMocking(): Promise<boolean> {
  const mocksEnabled =
    import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCKS === "true";

  if (!mocksEnabled) {
    return false;
  }

  const { worker } = await import("./mocks/browser");
  await worker.start({
    onUnhandledRequest: "bypass",
    serviceWorker: {
      url: "/mockServiceWorker.js",
    },
  });
  return false;
}

async function bootstrap() {
  if (await enableMocking()) {
    return;
  }

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
    },
  });
  const router = createAppRouter();
  const rootElement = document.getElementById("root");

  if (!rootElement) {
    throw new Error("Missing #root application mount.");
  }

  createRoot(rootElement).render(
    <StrictMode>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </ErrorBoundary>
    </StrictMode>,
  );
}

void bootstrap();
