"""Verify the P15 Candidate through the authenticated Knowledge API."""

from __future__ import annotations

from http.cookiejar import CookieJar
import json
import os
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


def validate_api_candidate(
    *,
    summary: Mapping[str, Any],
    detail: Mapping[str, Any],
) -> dict[str, str]:
    if (
        summary.get("status") != "author_confirmation_required"
        or detail.get("status") != "author_confirmation_required"
    ):
        raise RuntimeError("P15 Candidate must stop at author confirmation")
    candidate_id = summary.get("candidateId")
    invocation_id = detail.get("originModelInvocationId")
    evidence = detail.get("evidence")
    if (
        not isinstance(candidate_id, str)
        or detail.get("candidateId") != candidate_id
        or summary.get("candidateGroupId") != "candidate-poc-001"
        or summary.get("evidenceCount") != 1
        or not isinstance(invocation_id, str)
        or not isinstance(evidence, list)
        or len(evidence) != 1
        or not isinstance(evidence[0], dict)
        or not isinstance(evidence[0].get("evidenceId"), str)
    ):
        raise RuntimeError("P15 Candidate API lineage is invalid")
    return {
        "candidate_id": candidate_id,
        "evidence_id": evidence[0]["evidenceId"],
        "origin_model_invocation_id": invocation_id,
        "status": "author_confirmation_required",
    }


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _json_request(
    opener: Any,
    *,
    url: str,
    method: str = "GET",
    payload: Mapping[str, str] | None = None,
    origin: str,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "Origin": origin}
    if body is not None:
        headers.update(
            {
                "Content-Type": "application/json",
                "X-CSRF-Protection": "1",
            }
        )
    request = Request(url, data=body, headers=headers, method=method)
    with opener.open(request, timeout=10) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise RuntimeError("P15 API returned a non-object response")
    return decoded


def verify_p15_api() -> dict[str, str]:
    origin = os.environ.get("KNOWLEDGE_P15_API_ORIGIN", "http://p15-api:8788")
    prefix = f"{origin}/api/prerelease/v1"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    username = _required("KNOWLEDGE_ADMIN_USERNAME")
    initial_password = _required("KNOWLEDGE_ADMIN_PASSWORD")
    verifier_password = _required("KNOWLEDGE_P15_VERIFIER_PASSWORD")

    def login(password: str) -> dict[str, Any]:
        return _json_request(
            opener,
            url=f"{prefix}/auth/login",
            method="POST",
            payload={"username": username, "password": password},
            origin=origin,
        )

    try:
        login_response = login(initial_password)
        active_password = initial_password
    except HTTPError as error:
        if error.code != 401:
            raise
        login_response = login(verifier_password)
        active_password = verifier_password
    if login_response.get("data", {}).get("mustChangePassword") is True:
        _json_request(
            opener,
            url=f"{prefix}/auth/password/change",
            method="POST",
            payload={
                "currentPassword": active_password,
                "newPassword": verifier_password,
            },
            origin=origin,
        )
    collection = _json_request(
        opener,
        url=f"{prefix}/candidates",
        origin=origin,
    )
    items = collection.get("data", {}).get("items", [])
    matches = [
        item
        for item in items
        if isinstance(item, dict)
        and item.get("candidateGroupId") == "candidate-poc-001"
    ]
    if len(matches) != 1:
        raise RuntimeError("P15 API must expose exactly one POC Candidate")
    candidate_id = matches[0].get("candidateId")
    detail_response = _json_request(
        opener,
        url=f"{prefix}/candidates/{candidate_id}",
        origin=origin,
    )
    detail = detail_response.get("data")
    if not isinstance(detail, dict):
        raise RuntimeError("P15 Candidate detail is unavailable")
    return validate_api_candidate(summary=matches[0], detail=detail)


def main() -> None:
    print(json.dumps(verify_p15_api(), sort_keys=True))


if __name__ == "__main__":
    main()
