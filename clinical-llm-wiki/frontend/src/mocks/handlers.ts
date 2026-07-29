import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import {
  healthFixture,
  releaseFixture,
  sessionFixture,
  sourcesFixture,
  usersFixture,
} from "./fixtures";

export const handlers = [
  http.get(resolveApiPath(API_PATHS.session), () => HttpResponse.json(sessionFixture)),
  http.get(resolveApiPath(API_PATHS.health), () => HttpResponse.json(healthFixture)),
  http.get(resolveApiPath(API_PATHS.currentRelease), () => HttpResponse.json(releaseFixture)),
  http.get(resolveApiPath(API_PATHS.sources), () => HttpResponse.json(sourcesFixture)),
  http.get(resolveApiPath(API_PATHS.adminUsers), () => HttpResponse.json(usersFixture)),
];
