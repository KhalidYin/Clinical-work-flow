import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import {
  healthFixture,
  auditEventsFixture,
  cancelReceiptFixture,
  candidateDetailsFixture,
  candidatesFixture,
  processingRunsFixture,
  releaseFixture,
  relationDirectoryFixture,
  relationQueryFixture,
  retryReceiptFixture,
  sessionFixture,
  sourceRegistrationFixture,
  sourcesFixture,
  usersFixture,
  modelProfilesFixture,
  modelProfileRegistrationFixture,
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
  http.get(resolveApiPath(API_PATHS.relationQuery), ({ request }) => {
    const url = new URL(request.url);
    const nodeId = url.searchParams.get("node_id");
    const query = url.searchParams.get("q")?.toLocaleLowerCase() ?? "";
    if (nodeId) {
      return HttpResponse.json({
        ...relationQueryFixture,
        data: {
          ...relationQueryFixture.data,
          rootNodeId: nodeId,
        },
      });
    }
    const nodes = relationDirectoryFixture.data.nodes.filter((node) =>
      [node.stableKey, node.knowledgeType, node.claim ?? ""]
        .join(" ")
        .toLocaleLowerCase()
        .includes(query),
    );
    return HttpResponse.json({
      ...relationDirectoryFixture,
      data: {
        ...relationDirectoryFixture.data,
        nodes,
        totalNodes: nodes.length,
      },
    });
  }),
  http.get(resolveApiPath(API_PATHS.auditEvents), ({ request }) => {
    const url = new URL(request.url);
    const filters = {
      actor: url.searchParams.get("actor")?.toLocaleLowerCase() ?? "",
      action: url.searchParams.get("action")?.toLocaleLowerCase() ?? "",
      objectType: url.searchParams.get("object_type")?.toLocaleLowerCase() ?? "",
      result: url.searchParams.get("result")?.toLocaleLowerCase() ?? "",
    };
    const items = auditEventsFixture.data.items.filter(
      (event) =>
        event.actorId.toLocaleLowerCase().includes(filters.actor) &&
        event.action.toLocaleLowerCase().includes(filters.action) &&
        event.objectType.toLocaleLowerCase().includes(filters.objectType) &&
        (event.result ?? "").toLocaleLowerCase().includes(filters.result),
    );
    return HttpResponse.json({
      ...auditEventsFixture,
      data: {
        ...auditEventsFixture.data,
        items,
        total: items.length,
      },
    });
  }),
  http.get(
    resolveApiPath(`${API_PATHS.candidates}/:candidateId`),
    ({ params }) => {
      const fixture = candidateDetailsFixture[String(params.candidateId)];
      return fixture
        ? HttpResponse.json(fixture)
        : HttpResponse.json(
            {
              error: {
                code: "candidate_not_found",
                message: "The governed candidate does not exist.",
              },
              meta: candidatesFixture.meta,
            },
            { status: 404 },
          );
    },
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
  http.get(resolveApiPath(API_PATHS.adminModelProfiles), () =>
    HttpResponse.json(modelProfilesFixture),
  ),
  http.post(resolveApiPath(API_PATHS.adminModelProfiles), () =>
    HttpResponse.json(modelProfileRegistrationFixture, { status: 201 }),
  ),
];
