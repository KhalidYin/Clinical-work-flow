import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";

import "./app/theme.css";
import { createAppRouter } from "./router";

const MOCK_CLEANUP_RELOAD_KEY = "knowledgeLedgerMockCleanupReload";

async function enableMocking(): Promise<boolean> {
  const mocksEnabled =
    import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCKS === "true";

  if (!mocksEnabled) {
    if ("serviceWorker" in navigator) {
      const controlledByMock =
        navigator.serviceWorker.controller?.scriptURL.includes(
          "mockServiceWorker.js",
        ) ?? false;
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(
        registrations
          .filter((registration) =>
            [
              registration.active,
              registration.installing,
              registration.waiting,
            ].some((worker) => worker?.scriptURL.includes("mockServiceWorker.js")),
          )
          .map((registration) => registration.unregister()),
      );
      if (
        controlledByMock &&
        sessionStorage.getItem(MOCK_CLEANUP_RELOAD_KEY) !== "done"
      ) {
        sessionStorage.setItem(MOCK_CLEANUP_RELOAD_KEY, "done");
        window.location.reload();
        return true;
      }
      sessionStorage.removeItem(MOCK_CLEANUP_RELOAD_KEY);
    }
    return false;
  }

  sessionStorage.removeItem(MOCK_CLEANUP_RELOAD_KEY);
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
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  );
}

void bootstrap();
