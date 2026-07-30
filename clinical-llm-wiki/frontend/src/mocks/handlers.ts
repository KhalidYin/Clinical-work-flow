import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import {
  healthFixture,
  cancelReceiptFixture,
  candidatesFixture,
  processingRunsFixture,
  releaseFixture,
  retryReceiptFixture,
  sessionFixture,
  sourceRegistrationFixture,
  sourcesFixture,
  usersFixture,
} from "./fixtures";

export const handlers = [
  http.get(resolveApiPath(API_PATHS.session), () => HttpResponse.json(sessionFixture)),
  http.get(resolveApiPath(API_PATHS.health), () => HttpResponse.json(healthFixture)),
  http.get(resolveApiPath(API_PATHS.currentRelease), () => HttpResponse.json(releaseFixture)),
  http.get(resolveApiPath(API_PATHS.sources), () => HttpResponse.json(sourcesFixture)),
  http.post(resolveApiPath(API_PATHS.sources), () =>
    HttpResponse.json(sourceRegistrationFixture, { status: 202 }),
  ),
  http.get(resolveApiPath(API_PATHS.processingRuns), () =>
    HttpResponse.json(processingRunsFixture),
  ),
  http.get(resolveApiPath(API_PATHS.candidates), () =>
    HttpResponse.json(candidatesFixture),
  ),
  http.post(
    resolveApiPath(`${API_PATHS.processingRuns}/run-failed-002/steps/step-parse-text/retry`),
    () => HttpResponse.json(retryReceiptFixture, { status: 202 }),
  ),
  http.post(
    resolveApiPath(`${API_PATHS.processingRuns}/run-active-001/cancel`),
    () => HttpResponse.json(cancelReceiptFixture, { status: 202 }),
  ),
  http.get(resolveApiPath(API_PATHS.adminUsers), () => HttpResponse.json(usersFixture)),
];
