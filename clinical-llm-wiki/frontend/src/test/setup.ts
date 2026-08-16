import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "../mocks/server";

// Parallel CI workers can make an otherwise immediate MSW round-trip exceed the
// library's one-second default. Keep assertions bounded without making tests flaky.
configure({ asyncUtilTimeout: 3_000 });

Object.defineProperty(window, "scrollTo", {
  value: () => undefined,
  writable: true,
});

if (!globalThis.crypto?.randomUUID) {
  Object.defineProperty(globalThis, "crypto", {
    value: {
      ...globalThis.crypto,
      randomUUID: () =>
        "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
          const r = (Math.random() * 16) | 0;
          const v = c === "x" ? r : (r & 0x3) | 0x8;
          return v.toString(16);
        }),
    },
    writable: true,
  });
}

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  server.resetHandlers();
});

afterAll(() => server.close());
