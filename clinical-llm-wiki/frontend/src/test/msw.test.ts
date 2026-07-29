import { getJson } from "../api/client";
import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";

describe("prerelease MSW contract", () => {
  it("serves the session fixture through the same URL used by the API client", async () => {
    const response = await fetch(resolveApiPath(API_PATHS.session));
    const payload = (await response.json()) as {
      data: { actorId: string };
      meta: { fixture: boolean };
    };

    expect(response.ok).toBe(true);
    expect(payload.data.actorId).toBe("usr-ke-017");
    expect(payload.meta.fixture).toBe(true);
  });

  it("supports the API client abort signal used by TanStack Query", async () => {
    const controller = new AbortController();
    const response = await getJson<{ actorId: string }>(API_PATHS.session, controller.signal);

    expect(response.data.actorId).toBe("usr-ke-017");
  });
});
